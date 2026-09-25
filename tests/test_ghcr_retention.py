import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/ghcr_retention.py"
spec = importlib.util.spec_from_file_location("ghcr_retention", SCRIPT)
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


def manifest(**fields):
    raw = json.dumps(fields, separators=(",", ":")).encode()
    return retention.digest_of(raw), raw


def version(version_id, digest, *tags):
    return {"id": version_id, "name": digest,
            "metadata": {"container": {"tags": list(tags)}}}


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.amd64, amd64_raw = manifest(schemaVersion=2, config={"digest": "amd64"})
        self.arm64, arm64_raw = manifest(schemaVersion=2, config={"digest": "arm64"})
        self.attestation, attestation_raw = manifest(schemaVersion=2, config={"digest": "attestation"})
        self.amd64_index, amd64_index_raw = manifest(
            schemaVersion=2,
            manifests=[{"digest": self.amd64}, {"digest": self.attestation}],
        )
        self.arm64_index, arm64_index_raw = manifest(
            schemaVersion=2, manifests=[{"digest": self.arm64}],
        )
        self.latest, latest_raw = manifest(
            schemaVersion=2,
            manifests=[{"digest": self.amd64_index}, {"digest": self.arm64_index}],
        )
        self.old, old_raw = manifest(schemaVersion=2, config={"digest": "old"})
        self.raw = dict(zip(
            [self.amd64, self.arm64, self.attestation, self.amd64_index,
             self.arm64_index, self.latest, self.old],
            [amd64_raw, arm64_raw, attestation_raw, amd64_index_raw,
             arm64_index_raw, latest_raw, old_raw],
        ))
        self.versions = [
            version(1, self.latest, "latest"),
            version(2, self.amd64_index, "latest-amd64"),
            version(3, self.arm64_index, "latest-arm64"),
            version(4, self.amd64),
            version(5, self.arm64),
            version(6, self.attestation),
            version(7, self.old),
        ]

    def read(self, ref):
        if "@" in ref:
            return self.raw[ref.rsplit("@", 1)[1]]
        tag = ref.rsplit(":", 1)[1]
        digest = next(v["name"] for v in self.versions
                      if tag in v["metadata"]["container"]["tags"])
        return self.raw[digest]

    def test_keeps_tagged_indexes_and_all_descendants(self):
        candidates, tags = retention.select_candidates(
            self.versions, "ghcr.io/test/alt-c10f2-ansible", self.read)
        self.assertEqual([v["name"] for v in candidates], [self.old])
        self.assertEqual(set(tags), retention.REQUIRED_TAGS)

    def test_keeps_arbitrary_additional_tag(self):
        self.versions[-1]["metadata"]["container"]["tags"] = ["backup"]
        candidates, _ = retention.select_candidates(
            self.versions, "ghcr.io/test/alt-c10f2-ansible", self.read)
        self.assertEqual(candidates, [])

    def test_stops_when_a_tag_and_package_listing_disagree(self):
        def stale_read(ref):
            if ref.endswith(":latest"):
                return self.raw[self.old]
            return self.read(ref)

        with self.assertRaisesRegex(RuntimeError, "digest does not match"):
            retention.select_candidates(
                self.versions, "ghcr.io/test/alt-c10f2-ansible", stale_read)

    def test_stops_when_a_referenced_manifest_is_missing(self):
        def missing_read(ref):
            if ref.endswith(self.attestation):
                raise FileNotFoundError(ref)
            return self.read(ref)

        with self.assertRaises(FileNotFoundError):
            retention.select_candidates(
                self.versions, "ghcr.io/test/alt-c10f2-ansible", missing_read)

    def test_lists_every_page(self):
        pages = [[{"id": number} for number in range(100)], [{"id": 100}]]
        with patch.object(retention, "api_request", side_effect=pages) as request:
            result = retention.list_versions("token", "/users/test/packages/container/test")
        self.assertEqual(len(result), 101)
        self.assertEqual(request.call_count, 2)

    def test_stops_before_deletion_if_tags_change(self):
        changed = [dict(v) for v in self.versions]
        changed[0] = version(1, self.latest, "latest", "new-tag")
        with (patch.dict(os.environ, {"GITHUB_TOKEN": "token", "IMAGE_USER": "test"}),
              patch.object(sys, "argv", ["ghcr_retention.py"]),
              patch.object(retention, "package_path", return_value="/package"),
              patch.object(retention, "list_versions", side_effect=[self.versions, changed]),
              patch.object(retention, "docker_manifest", side_effect=self.read),
              patch.object(retention, "api_request") as request):
            with self.assertRaisesRegex(RuntimeError, "tags changed"):
                retention.main()
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
