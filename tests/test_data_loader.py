from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from data_loader import load_calculation_services_dataset


def test_load_calculation_services_dataset(sample_excel_path):
    dataset = load_calculation_services_dataset(sample_excel_path)

    assert len(dataset["services"]) == 1
    service = dataset["services"][0]
    assert service["class_name"] == "экспорт/сибур"
    assert service["service_name"] == "Комплексная/услуга 2"
    assert service["direct_cost"] == 1000
    assert service["total_cost"] > 0
    assert dataset["direct_detail_labels"]
    assert dataset["indirect_detail_labels"]
    assert dataset["inefficiency_detail_labels"]


def test_load_calculation_requires_named_sheet(tmp_path: Path):
    path = tmp_path / "other.xlsx"
    workbook = Workbook()
    workbook.active.title = "Прочее"
    workbook.save(path)

    with pytest.raises(ValueError, match="нет листа 'Калькуляция'"):
        load_calculation_services_dataset(path)
