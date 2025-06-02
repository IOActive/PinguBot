# Analyze Task

The `analyze_task` is responsible for analyzing user-uploaded test cases. It determines whether the test case causes a crash, identifies the crash type, and collects relevant metadata. This task is the entry point for processing user-uploaded test cases.

## Key Responsibilities

1. **Build Setup**:  
   Sets up the appropriate build (custom or regular) for the test case. If a specific revision is provided, it ensures the build matches the revision.

2. **Testcase Setup**:  
   Prepares the test case and its dependencies for execution. This includes setting up the file paths and initializing required environment variables.

3. **Crash Detection**:  
   Executes the test case and determines if it causes a crash. If a crash occurs, it collects the crash type, address, state, and stack trace.

4. **Security Analysis**:  
   Determines if the crash is a security issue and, if so, estimates its severity.

5. **Reproducibility Check**:  
   Tests whether the crash is reproducible or a one-time occurrence.

6. **Duplicate Detection**:  
   Checks if the test case is a duplicate of an existing one.

7. **Task Creation**:  
   Creates follow-up tasks such as minimization, regression testing, progression testing, and impact analysis.

## Workflow

1. **Initialization**:  
   - Resets memory tool options and environment variables.
   - Fetches the test case and crash information from the backend.

2. **Build Setup**:  
   - Sets up the appropriate build based on the crash revision or the latest available revision.

3. **Test Execution**:  
   - Runs the test case and captures the crash output.
   - If no crash occurs, marks the test case as unreproducible.

4. **Crash Analysis**:  
   - Analyzes the crash stack trace and determines its type, address, and state.
   - Checks if the crash is a security issue and estimates its severity.

5. **Metadata Update**:  
   - Updates the test case and crash metadata with the collected information.

6. **Task Creation**:  
   - Creates additional tasks for further processing, such as minimization and regression testing.

## Important Notes

- **Reproducibility**:  
  If the crash is not reproducible, the task retries on another bot to confirm the result.

- **Security Flag**:  
  The task determines whether the crash is a security issue and assigns a severity level if applicable.

- **Duplicate Handling**:  
  If the test case is a duplicate, it is marked as such, and no further tasks are created.

- **Error Handling**:  
  If the build setup fails or the test case is invalid, the task logs an error and retries or closes the test case.

