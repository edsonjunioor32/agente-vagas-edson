#!/usr/bin/env python3
import pipeline
from scoring_v2 import score_job, is_remote

# Substitui apenas a camada de aderência; coleta, normalização, filtros e outputs
# continuam centralizados no pipeline já validado.
pipeline.score_job = score_job
pipeline.is_remote = is_remote

if __name__ == "__main__":
    pipeline.main()
