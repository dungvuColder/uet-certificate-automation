"""Deploy BPMN (demo + to-be) và form lên Camunda.  Chạy: python src/deploy.py"""
from pathlib import Path

import camunda_api as api

ROOT = Path(__file__).resolve().parent.parent
FILES = [ROOT / "bpmn/demo/xac_nhan_sv_demo.bpmn", ROOT / "bpmn/to-be/xac_nhan_sv_tobe.bpmn",
         ROOT / "forms/duyet-yeu-cau.form", ROOT / "forms/phat-ban-cung.form",
         ROOT / "forms/to-be/nop-don-to-be.form",
         ROOT / "forms/to-be/duyet-yeu-cau-to-be.form"]

if __name__ == "__main__":
    print("Kết nối:", api.BASE_URL, "- broker:", len(api.topology().get("brokers", [])))
    result = api.deploy(FILES)
    print("Deployment key:", result["deploymentKey"])
    for d in result["deployments"]:
        print(" -", d)
