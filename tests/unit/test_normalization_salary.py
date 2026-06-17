from __future__ import annotations

from job_pilot.modules.ingestion.normalization import normalize_salary
from job_pilot.modules.job_posts.enums import SalaryPeriod


def test_normalize_salary_supports_common_text() -> None:
    """薪资规范化支持常见月薪、年薪、日薪和上下文文本。"""

    monthly_salary = normalize_salary("20-30K·14薪")
    yearly_salary = normalize_salary("USD 80k-120k/year")
    daily_salary = normalize_salary("150-200元/天")
    salary_with_context = normalize_salary("岗位描述：薪资 1.5-2万/月，经验不限")
    negotiable_salary = normalize_salary("Salary: negotiable")
    experience_text = normalize_salary("岗位要求：3-5年经验，负责从0到1建设后端系统")
    payroll_experience_text = normalize_salary(
        "Minimum of 2-4 years of payroll processing experience.",
    )

    assert monthly_salary.salary_text == "20-30K·14薪"
    assert monthly_salary.salary_min == 20000
    assert monthly_salary.salary_max == 30000
    assert monthly_salary.salary_currency == "CNY"
    assert monthly_salary.salary_period == SalaryPeriod.UNKNOWN
    assert yearly_salary.salary_min == 80000
    assert yearly_salary.salary_max == 120000
    assert yearly_salary.salary_currency == "USD"
    assert yearly_salary.salary_period == SalaryPeriod.YEAR
    assert daily_salary.salary_min == 150
    assert daily_salary.salary_max == 200
    assert daily_salary.salary_period == SalaryPeriod.DAY
    assert salary_with_context.salary_text == "1.5-2万/月"
    assert salary_with_context.salary_min == 15000
    assert salary_with_context.salary_max == 20000
    assert salary_with_context.salary_period == SalaryPeriod.MONTH
    assert negotiable_salary.salary_text == "Salary: negotiable"
    assert negotiable_salary.salary_min is None
    assert negotiable_salary.salary_max is None
    assert experience_text.salary_text is None
    assert payroll_experience_text.salary_text is None
