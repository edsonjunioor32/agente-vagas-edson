import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from scoring_v2 import score_job


def job(title, skills="", categories="", seniority="Pleno", work_model="remote", city="BR"):
    return {
        "title": title,
        "company": "Empresa",
        "description": "",
        "skills": skills,
        "categories": categories,
        "seniority": seniority,
        "work_model": work_model,
        "city": city,
        "contract_types": ["CLT"],
    }


class ScoringV2Tests(unittest.TestCase):
    def test_strong_n2_payments_fit_is_high(self):
        score, _ = score_job(job(
            "Analista de Suporte N2",
            "SQL · Oracle · APIs · Postman · Splunk · RCA · ITIL · pagamentos · cartões · webhooks",
            "Tecnologia"
        ))
        self.assertGreaterEqual(score, 85)

    def test_product_manager_is_not_false_positive(self):
        score, _ = score_job(job(
            "Product Manager | Digital Wallets & Apple Pay",
            "pagamentos cartões API",
            "Fintech"
        ))
        self.assertLessEqual(score, 30)

    def test_accent_synonyms_do_not_double_count(self):
        a, _ = score_job(job("Analista de Sustentação", "sustentação"))
        b, _ = score_job(job("Analista de Sustentação", "sustentação sustentacao"))
        self.assertEqual(a, b)

    def test_generic_customer_success_is_capped(self):
        score, _ = score_job(job("Customer Success Manager", "relacionamento clientes", "SaaS"))
        self.assertLessEqual(score, 35)

    def test_technical_customer_success_can_score_higher(self):
        score, _ = score_job(job("Customer Success", "API integrações SQL B2B", "SaaS"))
        self.assertGreater(score, 35)

    def test_n1_scores_lower_than_n2(self):
        common = "SQL API ITIL logs"
        n1, _ = score_job(job("Analista de Suporte N1", common))
        n2, _ = score_job(job("Analista de Suporte N2", common))
        self.assertLess(n1, n2)


if __name__ == "__main__":
    unittest.main()
