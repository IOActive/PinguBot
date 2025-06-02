# Minimize Task

The `minimize_task` is responsible for reducing the size and complexity of a test case while preserving its ability to reproduce a crash. This task ensures that the test case is as small and simple as possible, making it easier to analyze and debug.

## Key Responsibilities

1. **Crash Verification**:Ensures that the test case reliably reproduces the crash before starting minimization.
2. **Gesture Minimization**:Reduces the number of gestures required to reproduce the crash.
3. **File Minimization**:Minimizes the main test case file and any associated resources.
4. **Argument Minimization**:Reduces the command-line arguments required to reproduce the crash.
5. **Resource Minimization**:Minimizes additional resources, such as dependency files, used by the test case.
6. **Finalization**:
   Stores the minimized test case and creates follow-up tasks for further processing.

## Workflow

1. **Initialization**:

   - Sets up the test case and its dependencies.
   - Verifies that the crash is reproducible.
2. **Minimization Phases**:

   - **Gestures**: Reduces the number of gestures required to trigger the crash.
   - **Main File**: Minimizes the primary test case file.
   - **File List**: Minimizes the list of files associated with the test case.
   - **Resources**: Minimizes additional resources used by the test case.
   - **Arguments**: Reduces the command-line arguments required to reproduce the crash.
3. **Deadline Handling**:

   - If the task exceeds its deadline, it stores the partially minimized test case and retries later.
4. **Finalization**:

   - Stores the minimized test case in the backend.
   - Creates follow-up tasks such as regression testing and progression testing.

## Important Notes

- **Reproducibility**:The task ensures that the minimized test case still reproduces the crash.
- **Deadline Management**:If the task cannot complete within the allotted time, it stores the progress and retries later.
- **Specialized Minimization**:The task uses specialized strategies for certain file types, such as JavaScript and HTML.
- **Error Handling**:
  If the test case is unreproducible or the build setup fails, the task logs an error and retries or skips minimization.
