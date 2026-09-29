# Security Policy

## Overview

Knowledge AI is designed with security boundaries around authentication,
authorization, retrieval, agent execution, tool usage, and external actions.

## Security Controls

The platform includes:

- JWT authentication
- Server-side RBAC
- Document-level authorization
- Prompt-injection detection
- Secret detection
- Indirect injection detection
- Output validation
- Grounding validation
- Citation validation
- Tool authorization
- Risk-based tool policies
- Human approval workflows
- Memory isolation
- Network isolation
- Non-root containers
- Security regression tests

## Reporting a Vulnerability

Please do not publicly disclose security vulnerabilities before they
have been reviewed.

Open a private security report through GitHub or contact the repository
maintainer directly.

## Secrets

Never commit:

- API keys
- passwords
- JWT secrets
- database credentials
- production environment files

Use environment variables for credentials.