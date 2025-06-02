# Regression Task

The `regression_task` identifies the commit range where a regression was introduced. It uses binary search to narrow down the range of revisions that caused the crash.

## Key Responsibilities

1. **Build Setup**:  
   Sets up builds for specific revisions to test for the crash.

2. **Binary Search**:  
   Uses binary search to efficiently identify the regression range.

3. **Validation**:  
   Ensures that the identified regression range is accurate by testing earlier revisions.

4. **Task Creation**:  
   Creates follow-up tasks, such as blame analysis, based on the regression range.

## Workflow

1. **Initialization**:  
   - Fetches the test case and crash information.
   - Sets up the test case and its dependencies.

2. **Build Setup**:  
   - Sets up builds for the revisions to be tested.

3. **Binary Search**:  
   - Tests the crash at the middle revision of the current range.
   - Narrows the range based on whether the crash reproduces.

4. **Validation**:  
   - Tests earlier revisions to ensure the regression range is accurate.

5. **Finalization**:  
   - Saves the identified regression range.
   - Creates follow-up tasks for further analysis.

## Important Notes

- **Bad Builds**:  
  If a build is invalid, the task skips it and continues testing.

- **Validation**:  
  The task ensures that the regression range is accurate by testing additional revisions.

- **Error Handling**:  
  If the task cannot complete due to errors or timeouts, it retries later.

