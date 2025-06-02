# Progression Task

The `progression_task` determines whether a test case has been fixed in newer revisions. It identifies the range of revisions where the crash was resolved.

## Key Responsibilities

1. **Build Setup**:  
   Sets up builds for specific revisions to test for the crash.

2. **Binary Search**:  
   Uses binary search to efficiently identify the fixed range.

3. **Validation**:  
   Ensures that the identified fixed range is accurate by testing additional revisions.

4. **Task Creation**:  
   Creates follow-up tasks, such as regression testing, based on the fixed range.

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
   - Tests additional revisions to ensure the fixed range is accurate.

5. **Finalization**:  
   - Saves the identified fixed range.
   - Creates follow-up tasks for further analysis.

## Important Notes

- **Bad Builds**:  
  If a build is invalid, the task skips it and continues testing.

- **Validation**:  
  The task ensures that the fixed range is accurate by testing additional revisions.

- **Error Handling**:  
  If the task cannot complete due to errors or timeouts, it retries later.

