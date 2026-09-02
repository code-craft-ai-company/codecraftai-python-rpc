# Implementation Plan: Security

## Overview

Add TLS upgraders, the HELLO authenticator, attribute and reference isolation policies, and
the source-level safety test. Depends on Transport, Sessions and Object Proxies.

## Tasks

- [x] 1. Safe decoding guard
  - [x] 1.1 `test_security_no_pickle.py` scanning the serialization package for forbidden names
    - _Requirements: 3.1_

- [x] 2. TLS
  - [x] 2.1 Create `security/tls.py` with the three upgraders; verify by default; addresses preserved
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  - [x] 2.2 Accept loop logs and continues on handshake failure
    - _Requirements: 1.2_
  - [x] 2.3 Tests with a generated certificate: success, verification failure, mutual TLS identity
    - _Requirements: 1.1–1.5_

- [x] 3. Token handshake
  - [x] 3.1 `credential` on the client and in RequestHello; `authenticator` on the server; reject before reply; identity on session and call context
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6_
  - [x] 3.2 `shared_secret_authenticator`; HELLO timeout
    - _Requirements: 2.5, 2.7_
  - [x] 3.3 Audit logging
    - _Requirements: 4.1_
  - [x] 3.4 Tests: correct and wrong secret, identity visible, timeout on silent peer
    - _Requirements: 2.1–2.7, 4.1_

- [x] 4. Isolation and attribute policy
  - [x] 4.1 Per-peer reference resolution in the table and handlers
    - _Requirements: 3.2_
  - [x] 4.2 Create `security/policy.py`; underscore and root-write refusal; markers
    - _Requirements: 3.3, 3.4_
  - [x] 4.3 Configurable maximum message size on the server
    - _Requirements: 3.5_
  - [x] 4.4 Refusal logging
    - _Requirements: 4.2_
  - [x] 4.5 Tests: cross-client reference refused, private attribute refused, root write refused, size limit
    - _Requirements: 3.2–3.5, 4.2_

- [x] 5. Checkpoint - Ensure all tests pass
