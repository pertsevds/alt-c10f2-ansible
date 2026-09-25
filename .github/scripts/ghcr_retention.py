#!/usr/bin/env python3
"""Delete GHCR versions that are not reachable from any current image tag."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
REQUIRED_TAGS = {"latest", "latest-amd64", "latest-arm64"}
PACKAGE = "alt-c10f2-ansible"


def api_request(token, path, method="GET"):
    request = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method=method,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if method == "DELETE":
            if response.status != 204:
                raise RuntimeError(f"Unexpected delete status: {response.status}")
            return None
        return json.load(response)


def package_path(token, owner):
    owner_info = api_request(token, "/users/" + urllib.parse.quote(owner, safe=""))
    if owner_info["type"] == "Organization":
        return "/orgs/" + urllib.parse.quote(owner, safe="") + "/packages/container/" + PACKAGE
    if owner_info["type"] == "User":
        return "/users/" + urllib.parse.quote(owner, safe="") + "/packages/container/" + PACKAGE
    raise RuntimeError("Unknown GitHub package owner type")


def list_versions(token, path):
    versions = []
    page = 1
    while True:
        batch = api_request(token, f"{path}/versions?per_page=100&page={page}")
        if not isinstance(batch, list):
            raise RuntimeError("Package versions response is not a list")
        versions.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return versions


def parse_versions(versions):
    by_id = {}
    by_digest = {}
    tags = {}
    for version in versions:
        version_id = version["id"]
        digest = version["name"]
        version_tags = version["metadata"]["container"]["tags"]
        if not isinstance(version_id, int) or not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise RuntimeError("Invalid GHCR package version")
        if not isinstance(version_tags, list) or not all(isinstance(tag, str) and tag for tag in version_tags):
            raise RuntimeError("Invalid GHCR package tags")
        if version_id in by_id or digest in by_digest:
            raise RuntimeError("Duplicate GHCR package version")
        by_id[version_id] = version
        by_digest[digest] = version
        for tag in version_tags:
            if tag in tags:
                raise RuntimeError(f"Duplicate GHCR tag: {tag}")
            tags[tag] = digest
    if not REQUIRED_TAGS.issubset(tags):
        raise RuntimeError("Required image tags are missing from GHCR package versions")
    return by_id, by_digest, tags


def docker_manifest(ref):
    return subprocess.check_output(
        ["docker", "buildx", "imagetools", "inspect", "--raw", ref],
        stderr=subprocess.PIPE,
        timeout=90,
    )


def digest_of(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def select_candidates(versions, image, read_manifest=docker_manifest):
    by_id, by_digest, tags = parse_versions(versions)
    protected = set()
    inspected = set()

    def visit(ref, expected, verify_again=False):
        if expected in inspected and not verify_again:
            return
        raw = read_manifest(ref)
        if digest_of(raw) != expected:
            raise RuntimeError(f"Registry digest does not match {ref}")
        if expected in inspected:
            return
        manifest = json.loads(raw)
        if not isinstance(manifest, dict):
            raise RuntimeError(f"Invalid OCI manifest: {ref}")
        inspected.add(expected)
        protected.add(expected)
        children = manifest.get("manifests", [])
        if not isinstance(children, list):
            raise RuntimeError(f"Invalid OCI index: {ref}")
        for child in children:
            digest = child["digest"]
            if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
                raise RuntimeError(f"Invalid OCI child digest: {ref}")
            visit(f"{image}@{digest}", digest)

    for tag, digest in tags.items():
        visit(f"{image}:{tag}", digest, verify_again=True)

    # Registry children can be absent from the Packages API; they are still protected.
    return [version for version in by_id.values()
            if not version["metadata"]["container"]["tags"]
            and version["name"] not in protected], tags


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="list candidates without deleting")
    args = parser.parse_args()
    token = os.environ["GITHUB_TOKEN"]
    owner = os.environ["IMAGE_USER"]
    image = f"ghcr.io/{owner}/{PACKAGE}"
    path = package_path(token, owner)
    versions = list_versions(token, path)
    candidates, tags = select_candidates(versions, image, docker_manifest)
    print(f"Protected {len(tags)} tags; found {len(candidates)} unreferenced versions")
    for version in candidates:
        print(f"Candidate: {version['name']} (version {version['id']})")

    # Abort if a tag changed during inspection, rather than act on a stale graph.
    _, _, current_tags = parse_versions(list_versions(token, path))
    if current_tags != tags:
        raise RuntimeError("GHCR tags changed during cleanup; retry on the next release")

    if args.dry_run:
        print("Dry run: no versions deleted")
        return

    deleted = 0
    for version in candidates:
        version_id = version["id"]
        current = api_request(token, f"{path}/versions/{version_id}")
        if current["name"] != version["name"] or current["metadata"]["container"]["tags"]:
            raise RuntimeError(f"Package version {version_id} changed during cleanup")
        api_request(token, f"{path}/versions/{version_id}", method="DELETE")
        deleted += 1
    print(f"Deleted {deleted} unreferenced GHCR package versions")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, OSError, urllib.error.URLError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError) as error:
        print(f"GHCR cleanup stopped: {error}", file=sys.stderr)
        sys.exit(1)
