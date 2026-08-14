import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from scoring_v2 import score_job


def job(title, skills="", categories="", seniority="Pleno", work_model="remote", city="BR", description=""):
    return {
        "title": title,
        "company": "Empresa",
        "description": description,
        "skills": skills,
        "categories": categories,
        "seniority": seniority,
        "work_model": work_model,
        "city": city,
        "contract_types": ["CLT"],
    }


class ScoringV3Tests(unittest.TestCase):
    def test_strong_n2_payments_fit_is_high_and_well_covered(self):
        item = job(
            "Analista de Suporte N2",
            "SQL · Oracle · APIs · Postman · Splunk · RCA · ITIL · pagamentos · cartões · webhooks",
            "Tecnologia"
        )
        score, _ = score_job(item)
        self.assertGreaterEqual(score, 85)
        self.assertGreaterEqual(item["coverage"], 80)

    def test_sparse_n2_is_not_penalized_for_missing_snapshot_fields(self):
        item = job("Analista de Suporte à Aplicações N2", skills="", categories="", seniority="")
        score, _ = score_job(item)
        self.assertGreaterEqual(score, 80)
        self.assertLess(item["coverage"], 60)

    def test_explicit_skills_make_technical_block_fully_evaluable(self):
        sparse = job("Analista de Suporte N2", skills="", seniority="")
        rich = job("Analista de Suporte N2", skills="Excel atendimento", seniority="")
        sparse_score, _ = score_job(sparse)
        rich_score, _ = score_job(rich)
        self.assertLess(rich_score, sparse_score)
        self.assertGreater(rich["coverage"], sparse["coverage"])

    def test_product_manager_is_not_false_positive(self):
        item = job("Product Manager | Digital Wallets & Apple Pay", "pagamentos cartões API", "Fintech")
        score, _ = score_job(item)
        self.assertLessEqual(score, 30)

    def test_accent_synonyms_do_not_double_count(self):
        a = job("Analista de Sustentação", "sustentação")
        b = job("Analista de Sustentação", "sustentação sustentacao")
        score_a, _ = score_job(a)
        score_b, _ = score_job(b)
        self.assertEqual(score_a, score_b)
        self.assertEqual(a["coverage"], b["coverage"])

    def test_generic_customer_success_is_capped(self):
        item = job("Customer Success Manager", "relacionamento clientes", "SaaS")
        score, _ = score_job(item)
        self.assertLessEqual(score, 35)

    def test_technical_customer_success_can_score_higher(self):
        item = job("Customer Success", "API integrações SQL B2B", "SaaS")
        score, _ = score_job(item)
        self.assertGreater(score, 35)

    def test_n1_scores_lower_than_n2(self):
        common = "SQL API ITIL logs"
        n1 = job("Analista de Suporte N1", common)
        n2 = job("Analista de Suporte N2", common)
        score_n1, _ = score_job(n1)
        score_n2, _ = score_job(n2)
        self.assertLess(score_n1, score_n2)

    def test_short_alias_api_uses_word_boundary(self):
        false_hit = job("Analista de Suporte", "capital humano")
        true_hit = job("Analista de Suporte", "API REST")
        score_job(false_hit)
        score_job(true_hit)
        self.assertLess(false_hit["coverage"], true_hit["coverage"])

    def test_coverage_is_always_valid_percentage(self):
        item = job("Analista de Suporte", seniority="")
        score, _ = score_job(item)
        self.assertTrue(0 <= score <= 100)
        self.assertTrue(0 <= item["coverage"] <= 100)
        self.assertEqual(item["score_method"], "observed_evidence_v3")


if __name__ == "__main__":
    unittest.main()
