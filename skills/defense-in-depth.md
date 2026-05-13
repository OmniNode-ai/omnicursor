---
name: "onex:defense-in-depth"
description: >-
  Use this skill when fixing a bug caused by invalid data reaching deep into execution. The goal is to add validation at every layer the data passes through, making the bug structurally impossible to reproduce.
disable-model-invocation: true
---

# onex:defense-in-depth

Use this skill when fixing a bug caused by invalid data reaching deep into execution. The goal is to add validation at every layer the data passes through, making the bug structurally impossible to reproduce.

## Purpose

A single validation point feels sufficient but can be bypassed by different code paths, refactoring, or mocks. This skill ensures that invalid data is caught at every layer, not just one.

## Prerequisites

- A bug caused by invalid or unexpected data
- Understanding of the data flow from entry point to failure site

## Workflow

1. **Trace the data flow.**
   Start from where the bad value originates and follow it through every function and module until the failure. List each checkpoint the data passes through.

2. **Add Layer 1: Entry point validation.**
   At the API boundary or public function where data enters, reject obviously invalid input. Check for: empty values, wrong types, missing required fields, and values outside valid ranges.

3. **Add Layer 2: Business logic validation.**
   Inside the core logic that consumes the data, verify it makes sense for the specific operation. This catches cases where entry validation passed but the value is semantically wrong for this context.

4. **Add Layer 3: Environment guards.**
   Add context-specific protections. For example: refuse destructive operations outside temp directories during tests, block production writes in development mode, or reject paths outside the workspace root.

5. **Add Layer 4: Debug instrumentation.**
   Add logging at the point closest to the failure with enough context for forensics: the invalid value, the call stack, and the current environment. This layer catches whatever the other three missed.

6. **Test each layer independently.**
   Write tests that bypass Layer 1 and verify Layer 2 catches the bad data. Write tests that bypass both and verify Layer 3 catches it. Confirm Layer 4 logs the right context.

## Expected Output Format

For each bug fix:
- Data flow trace (entry point to failure site)
- Four validation layers with code
- Tests proving each layer catches the defect independently

## Quality Checklist

- [ ] Data flow is fully traced from origin to failure
- [ ] Layer 1 validates at the entry point (API boundary)
- [ ] Layer 2 validates at the business logic level
- [ ] Layer 3 adds environment-specific guards
- [ ] Layer 4 adds debug logging with call context
- [ ] Each layer is tested independently
