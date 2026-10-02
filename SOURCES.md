# Source strategy

## Direct ATS sources
- Greenhouse: public Job Board GET API; no authentication required for public GET endpoints.
- Ashby: public Job Postings API for currently published job postings.
- SmartRecruiters: company postings endpoint.
- Lever: public postings endpoint.

## Aggregators
Remote OK, Remotive, and one page of Arbeitnow are retained as supplemental discovery feeds.

## Expansion
Add companies to `config/sources.json` using the ATS board slug shown by the company's official careers URL. Do not add guessed slugs; failed sources are reported in the collection output.
