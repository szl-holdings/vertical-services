# estate-holo HF Space mirror (bootstrap source-of-record)

HF Space: SZLHOLDINGS/estate-holo, pinned revision 187c999950740ccf4487457390491c89c9ce9ad3 (baseline r1.1 pin, recorded 2026-11-23).

snapshot/ = byte-exact capture of the Space at the pinned revision; every file sha256-asserted at acquisition on 2026-11-23:

| File | Size (B) | SHA-256 |
|---|---|---|
| .gitattributes | 1519 | 11ad7efa24975ee4b0c3c3a38ed18737f0658a5f75a0a96787b576a78a023361 |
| Dockerfile | 277 | 01fa437c14e0d1af740ddb2d7fa0f2fedd3aedbf9c731f0ce467e220900aa2c0 |
| README.md | 1608 | 97574d6c9c25ef0c468c6824731600613e82372fc9dc4df44042b83de99e9ae1 |
| app.py | 2809 | 53eacc098c8af65e5c18654891616500e53f5ff796ebcab58ae24a299b19c5f1 |
| assets/szl-card/mesh-receipts.svg | 6007 | e2ec8f99d35ccdaa3a2a7d2efc1551f186e53012ff84b56dbc994b36fef659db |
| assets/szl-card/org-context.svg | 1744 | cd7090a350bed6168133489b1f97e4968c0320d8961fec08e7d9950bfd6ea23f |
| index.html | 16715 | 60027c58622fec5ea551cd223d4fdc7b4c84b35be2c0fd2e68b2e4d237911a83 |
| tests/test_holo3d_contract.py | 4333 | 0f28a970be54590e3771383cf17b966f820074be44aeffc372dadbd5ca5ac8a4 |

Declared development source: szl-holdings/vertical-services (this repository). The Space README declares: client adapted from vertical-services holo3d.py v1.1 (PRs #131 + #132, commits 6a3f261 + e7da36ae); contract test tests/test_holo3d_contract.py.

Honest boundary: the Space app.py does NOT byte-match deploy/app.py nor deploy/szl_verticals/holo3d.py at repository head; this mirror records a deployment derivative, NOT verbatim synchronization with either file or with the repository head.

Propose-only, no-merge; merge decisions are owner-gated behind the estate signature wall. Kimi q8 A ruling: MAPPED_BY_DECLARED_LINEAGE, GO_OPTION_2.
