# Symbolize Task

The `symbolize_task` generates symbolized stack traces for crashes. It uses debug and release builds to provide detailed crash information.

## Key Responsibilities

1. **Build Setup**:  
   Sets up symbolized debug and release builds for the test case.

2. **Crash Reproduction**:  
   Reproduces the crash using the symbolized builds.

3. **Stack Trace Generation**:  
   Generates detailed stack traces for the crash.

4. **Metadata Update**:  
   Updates the test case and crash metadata with the symbolized stack trace.

## Workflow

1. **Initialization**:  
   - Fetches the test case and crash information.
   - Sets up the test case and its dependencies.

2. **Build Setup**:  
   - Sets up symbolized debug and release builds.

3. **Crash Reproduction**:  
   - Reproduces the crash using the symbolized builds.

4. **Stack Trace Generation**:  
   - Generates detailed stack traces for the crash.

5. **Finalization**:  
   - Updates the test case and crash metadata with the symbolized stack trace.

## Important Notes

- **Debug and Release Builds**:  
  The task uses both debug and release builds to generate detailed stack traces.

- **Error Handling**:  
  If the task cannot complete due to errors or timeouts, it retries later.

