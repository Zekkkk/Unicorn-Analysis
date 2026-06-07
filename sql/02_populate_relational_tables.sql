-- Populate the normalized PostgreSQL tables from staging_unicorn_companies.
-- First import data/Unicorn_Companies.csv into staging_unicorn_companies with CSV header enabled.

INSERT INTO countries (country_name)
SELECT DISTINCT TRIM(country)
FROM staging_unicorn_companies
WHERE country IS NOT NULL AND TRIM(country) <> ''
ON CONFLICT (country_name) DO NOTHING;

INSERT INTO industries (industry_name)
SELECT DISTINCT TRIM(industry)
FROM staging_unicorn_companies
WHERE industry IS NOT NULL AND TRIM(industry) <> ''
ON CONFLICT (industry_name) DO NOTHING;

INSERT INTO cities (city_name, country_id)
SELECT DISTINCT
    TRIM(s.city),
    c.country_id
FROM staging_unicorn_companies s
JOIN countries c ON c.country_name = TRIM(s.country)
WHERE s.city IS NOT NULL
  AND TRIM(s.city) <> ''
ON CONFLICT (city_name, country_id) DO NOTHING;

INSERT INTO companies (
    company_name,
    valuation_b,
    date_joined,
    founded_year,
    total_raised,
    financial_stage,
    investors_count,
    deal_terms,
    portfolio_exits,
    country_id,
    city_id,
    industry_id
)
SELECT
    TRIM(s.company),
    REPLACE(REPLACE(s.valuation_raw, '$', ''), ',', '')::NUMERIC(10,2),
    TO_DATE(s.date_joined_raw, 'MM/DD/YYYY'),
    NULLIF(NULLIF(TRIM(s.founded_year_raw), ''), 'None')::INTEGER,
    s.total_raised,
    NULLIF(NULLIF(TRIM(s.financial_stage), ''), 'None'),
    NULLIF(NULLIF(TRIM(s.investors_count_raw), ''), 'None')::INTEGER,
    s.deal_terms,
    s.portfolio_exits,
    c.country_id,
    ci.city_id,
    i.industry_id
FROM staging_unicorn_companies s
JOIN countries c ON c.country_name = TRIM(s.country)
JOIN industries i ON i.industry_name = TRIM(s.industry)
LEFT JOIN cities ci
    ON ci.city_name = TRIM(s.city)
   AND ci.country_id = c.country_id
WHERE s.company IS NOT NULL
  AND TRIM(s.company) <> ''
ON CONFLICT (company_name) DO NOTHING;

INSERT INTO investors (investor_name)
SELECT DISTINCT TRIM(split_investor.name)
FROM staging_unicorn_companies s
CROSS JOIN LATERAL regexp_split_to_table(s.select_investors, ',') AS split_investor(name)
WHERE s.select_investors IS NOT NULL
  AND TRIM(s.select_investors) <> ''
  AND TRIM(split_investor.name) <> ''
  AND TRIM(split_investor.name) <> 'None'
ON CONFLICT (investor_name) DO NOTHING;

INSERT INTO company_investors (company_id, investor_id)
SELECT DISTINCT
    c.company_id,
    i.investor_id
FROM staging_unicorn_companies s
JOIN companies c
    ON c.company_name = TRIM(s.company)
CROSS JOIN LATERAL regexp_split_to_table(s.select_investors, ',') AS split_investor(name)
JOIN investors i
    ON i.investor_name = TRIM(split_investor.name)
WHERE s.select_investors IS NOT NULL
  AND TRIM(s.select_investors) <> ''
  AND TRIM(split_investor.name) <> ''
  AND TRIM(split_investor.name) <> 'None'
ON CONFLICT (company_id, investor_id) DO NOTHING;

-- Population evidence query for the project report.
SELECT 'staging' AS table_name, COUNT(*) FROM staging_unicorn_companies
UNION ALL
SELECT 'countries', COUNT(*) FROM countries
UNION ALL
SELECT 'cities', COUNT(*) FROM cities
UNION ALL
SELECT 'industries', COUNT(*) FROM industries
UNION ALL
SELECT 'companies', COUNT(*) FROM companies
UNION ALL
SELECT 'investors', COUNT(*) FROM investors
UNION ALL
SELECT 'company_investors', COUNT(*) FROM company_investors;

-- Join proof query showing the relational tables working together.
SELECT
    c.company_name,
    c.valuation_b,
    co.country_name,
    ci.city_name,
    i.industry_name,
    COUNT(cin.investor_id) AS investor_count_from_join
FROM companies c
JOIN countries co ON c.country_id = co.country_id
LEFT JOIN cities ci ON c.city_id = ci.city_id
JOIN industries i ON c.industry_id = i.industry_id
LEFT JOIN company_investors cin ON c.company_id = cin.company_id
GROUP BY c.company_id, c.company_name, c.valuation_b, co.country_name, ci.city_name, i.industry_name
ORDER BY c.valuation_b DESC
LIMIT 10;
