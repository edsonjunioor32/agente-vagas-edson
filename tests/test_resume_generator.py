import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import resume_generator as rg
import scoring_v2


class ResumeGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = json.loads((ROOT / "resume" / "base_profile.json").read_text(encoding="utf-8"))

    def test_requested_unverified_skills_are_reported_not_added(self):
        job = {
            "title": "Analista de Suporte .NET N2",
            "company": "Empresa Teste",
            "description": "Suporte N2, sustentação, SQL, análise de logs, C#, .NET e Linux.",
            "work_model": "remote",
            "seniority": "Pleno",
        }
        matched, gaps = rg.analyze(job, self.profile)
        self.assertIn("Suporte N2", matched)
        self.assertIn("Sustentação de Sistemas", matched)
        self.assertIn("SQL", matched)
        self.assertIn("Logs", matched)
        self.assertIn(".NET/C#", gaps)
        self.assertIn("Linux", gaps)

        tex = rg.build_tex(job, self.profile, matched)
        self.assertIn("SQL", tex)
        self.assertNotIn("ASP.NET", tex)
        self.assertNotIn("C\\#", tex)
        self.assertNotIn("Linux", tex)

    def test_latex_special_characters_are_escaped(self):
        self.assertEqual(rg.latex("C&A 100% #1"), r"C\&A 100\% \#1")

    def test_job_selection_is_one_based(self):
        payload = {"jobs": [{"title": "Primeira"}, {"title": "Segunda"}]}
        self.assertEqual(rg.select_job(payload, 2, "")["title"], "Segunda")

    def test_generated_latex_has_expected_ats_structure(self):
        job = {
            "title": "Analista de Suporte N2",
            "company": "Empresa Teste",
            "description": "Suporte N2, SQL, APIs, incidentes, RCA, logs, SLA e documentação técnica.",
            "work_model": "remote",
            "seniority": "Pleno",
        }
        matched, _ = rg.analyze(job, self.profile)
        tex = rg.build_tex(job, self.profile, matched)
        self.assertIn(r"\documentclass[a4paper,11pt]{article}", tex)
        self.assertIn(r"\usepackage{cmap}", tex)
        self.assertIn(r"\pdfgentounicode=1", tex)
        self.assertIn(r"\cvsection{Experiência Profissional}", tex)
        self.assertNotIn(r"\begin{tabular}", tex)
        self.assertNotIn(r"\begin{multicols}", tex)

    def test_database_phrase_does_not_count_as_banking_domain(self):
        points, covered, label = scoring_v2._domain_evidence(scoring_v2.norm("software SaaS com consultas em banco de dados"))
        self.assertEqual((points, covered, label), (11, 15, "tecnologia/SaaS"))

    def test_explicit_financial_domain_still_counts(self):
        points, covered, label = scoring_v2._domain_evidence(scoring_v2.norm("fintech de meios de pagamento e cartões"))
        self.assertEqual((points, covered, label), (15, 15, "financeiro/pagamentos"))


if __name__ == "__main__":
    unittest.main()
