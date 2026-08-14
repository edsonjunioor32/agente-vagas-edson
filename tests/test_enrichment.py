import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from enrichment import (
    extract_description_from_html, extract_inhire_description,
    parse_inhire_url, walk_jobposting,
)


class EnrichmentTests(unittest.TestCase):
    def test_extracts_jsonld_jobposting(self):
        html = '''
        <html><head><script type="application/ld+json">
        {"@context":"https://schema.org","@type":"JobPosting",
         "description":"<p>Atuar com suporte N2, SQL, APIs, webhooks, logs, incidentes e troubleshooting. Experiência com clientes B2B e integrações de sistemas. Responsável por análise técnica, diagnóstico e resolução de problemas complexos.</p>",
         "qualifications":"Conhecimento em SQL, APIs REST, Postman e observabilidade."}
        </script></head><body><div>vaga</div></body></html>
        '''
        description, method = extract_description_from_html(html)
        self.assertEqual(method, "json-ld")
        self.assertIn("suporte N2", description)
        self.assertIn("Postman", description)

    def test_html_fallback_requires_substantial_text(self):
        body = " ".join(["Analista de suporte técnico responsável por atendimento, diagnóstico, incidentes, APIs, SQL e integrações."] * 12)
        description, method = extract_description_from_html(f"<html><body><main>{body}</main></body></html>")
        self.assertEqual(method, "html-text")
        self.assertGreater(len(description), 700)

    def test_walks_graph_for_jobposting(self):
        data = {"@graph": [{"@type": "Organization", "name": "X"}, {"@type": "JobPosting", "description": "abc"}]}
        posting = walk_jobposting(data)
        self.assertEqual(posting["@type"], "JobPosting")

    def test_short_page_is_not_false_description(self):
        description, method = extract_description_from_html("<html><body>Vaga de suporte</body></html>")
        self.assertEqual(description, "")
        self.assertEqual(method, "")

    def test_parses_inhire_public_job_url(self):
        parsed = parse_inhire_url("https://matera.inhire.app/vagas/fb593c1a-f1d3-4f37-8675-e300551cd2d2/analista-de-suporte")
        self.assertEqual(parsed, ("matera", "fb593c1a-f1d3-4f37-8675-e300551cd2d2"))

    def test_rejects_non_inhire_url(self):
        self.assertIsNone(parse_inhire_url("https://example.com/vagas/123/teste"))

    def test_extracts_inhire_detail_description(self):
        detail = {
            "description": "<p>Suporte N2 com SQL, Oracle, APIs REST, logs, incidentes, integrações e atendimento B2B.</p>" * 4,
            "requirements": "Conhecimento de Postman, webhooks e troubleshooting."
        }
        description = extract_inhire_description(detail)
        self.assertIn("Suporte N2", description)
        self.assertIn("Postman", description)
        self.assertGreaterEqual(len(description), 180)


if __name__ == "__main__":
    unittest.main()
