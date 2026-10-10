"""Distributed reference integrity only; no candidate transformations are assessed."""
import hashlib
import json
import unittest
from urllib.parse import unquote

from normalization.references import ROOT, load_reference


def resolve_pointer(document, pointer):
    """Resolve a local JSON Pointer, including escaped keys and array indices."""
    pointer = unquote(pointer[1:] if pointer.startswith("#") else pointer)
    if not pointer:
        return document
    if not pointer.startswith("/"):
        raise ValueError("Expected a local JSON Pointer")
    node = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def walk(node):
    yield node
    if isinstance(node, dict):
        for child in node.values():
            yield from walk(child)
    elif isinstance(node, list):
        for child in node:
            yield from walk(child)


class ReferenceIntegrityChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = load_reference("prismhr")
        cls.base = ROOT / "contracts" / "prismhr"
        cls.path = cls.base / "openapi" / cls.reference["openapi"]["relative_path"]
        cls.payload = cls.path.read_bytes()
        cls.document = json.loads(cls.payload)

    def test_distributed_contract_matches_recorded_checksum_and_license(self):
        self.assertEqual(hashlib.sha256(self.payload).hexdigest(),
                         self.reference["openapi"]["sha256"])
        self.assertEqual(self.document["info"]["version"],
                         self.reference["openapi"]["version"])
        self.assertEqual(self.document["info"]["license"]["name"], "Apache 2.0 License")
        license_text = (self.base / self.reference["distribution"]["license_file"]).read_text()
        self.assertIn("Version 2.0, January 2004", license_text)
        self.assertTrue((self.base / "NOTICE.md").is_file())

    def test_internal_schema_references_resolve_and_examples_are_removed(self):
        for node in walk(self.document):
            if isinstance(node, dict):
                self.assertNotIn("example", node)
                self.assertNotIn("examples", node)
                if "$ref" in node:
                    with self.subTest(reference=node["$ref"]):
                        self.assertTrue(node["$ref"].startswith("#/"))
                        resolve_pointer(self.document, node["$ref"])

    def test_lookup_citations_match_the_distributed_source_descriptions(self):
        for domain in self.reference["lookups"]:
            self.assertTrue(domain["completeness"])
            for pointer in domain["source_field_pointers"]:
                resolve_pointer(self.document, pointer)
            for entry in domain["entries"]:
                with self.subTest(domain=domain["domain"], code=entry["code"]):
                    relative, pointer = entry["evidence_reference"].split("#", 1)
                    self.assertEqual((self.base / relative).resolve(), self.path.resolve())
                    description = resolve_pointer(self.document, pointer)
                    self.assertEqual(description, domain["source_description"])
                    self.assertIsInstance(entry["code"], str)
                    self.assertTrue(entry["meaning"])


if __name__ == "__main__":
    unittest.main()
