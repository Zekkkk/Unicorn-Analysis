-- PostgreSQL relational schema for the Unicorn Analysis project.
-- Run this in the unicorn_analysis database before importing the CSV.

CREATE TABLE staging_unicorn_companies (
    company TEXT,
    valuation_raw TEXT,
    date_joined_raw TEXT,
    country TEXT,
    city TEXT,
    industry TEXT,
    select_investors TEXT,
    founded_year_raw TEXT,
    total_raised TEXT,
    financial_stage TEXT,
    investors_count_raw TEXT,
    deal_terms TEXT,
    portfolio_exits TEXT
);

CREATE TABLE countries (
    country_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    country_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE cities (
    city_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    city_name VARCHAR(120) NOT NULL,
    country_id INTEGER NOT NULL REFERENCES countries(country_id),
    UNIQUE (city_name, country_id)
);

CREATE TABLE industries (
    industry_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    industry_name VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE companies (
    company_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_name VARCHAR(200) NOT NULL UNIQUE,
    valuation_b NUMERIC(10,2) NOT NULL CHECK (valuation_b >= 1),
    date_joined DATE NOT NULL,
    founded_year INTEGER CHECK (founded_year >= 1800),
    total_raised TEXT,
    financial_stage VARCHAR(80),
    investors_count INTEGER CHECK (investors_count >= 0),
    deal_terms TEXT,
    portfolio_exits TEXT,
    country_id INTEGER NOT NULL REFERENCES countries(country_id),
    city_id INTEGER REFERENCES cities(city_id),
    industry_id INTEGER NOT NULL REFERENCES industries(industry_id)
);

CREATE TABLE investors (
    investor_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    investor_name VARCHAR(200) NOT NULL UNIQUE
);

CREATE TABLE company_investors (
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    investor_id INTEGER NOT NULL REFERENCES investors(investor_id) ON DELETE CASCADE,
    PRIMARY KEY (company_id, investor_id)
);
