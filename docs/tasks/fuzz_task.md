# Fuzz Task

The `fuzz_task` is responsible for running fuzzing sessions to discover crashes and vulnerabilities in the target application. It supports multiple fuzzing strategies, including engine-based fuzzing, blackbox fuzzing, and two-stage blackbox fuzzing.

## Key Responsibilities

1. **Fuzzing Session Management**:Orchestrates fuzzing sessions using the selected fuzzing strategy.
2. **Corpus Management**:Synchronizes the corpus with the backend and uploads new test cases generated during fuzzing.
3. **Crash Detection**:Identifies crashes and collects relevant metadata, such as stack traces and crash states.
4. **Coverage Collection**:Uploads coverage data for the fuzzing session to the backend.
5. **Task Creation**:
   Creates follow-up tasks for crashes, such as minimization, regression testing, and progression testing.

## Supported Fuzzing Strategies

1. **Engine-Based Fuzzing**:Uses fuzzing engines like libFuzzer to generate inputs and test the target application. This strategy is ideal for structured input formats.
2. **Blackbox Fuzzing**:Runs the target application as a blackbox, generating random inputs without requiring knowledge of the internal structure. This approach is suitable for testing APIs, web services, or applications with unstructured input.
3. **Two-Stage Blackbox Fuzzing**:
   Combines blackbox fuzzing with a secondary stage of input refinement. The first stage generates random inputs, while the second stage focuses on inputs that trigger interesting behaviors or crashes.

## Adding a Blackbox Fuzzer

To integrate a custom blackbox fuzzer with PinguBot, the fuzzer must support the following command-line parameters:

- **`--input_dir`**: Specifies the directory containing input files for the fuzzer (corpus directory).
- **`--testcase_dir`**: Specifies the directory where the fuzzer should save test cases that cause crashes for reproduction.
- **`--artifacts_dir`**: Specifies the directory where the fuzzer should save miscellaneous output files, such as `.cov` files, which will be stored in the backend system after the fuzzing session.

### Corrected Middleware Script

If your fuzzer does not natively support these parameters, you can use a bash script as middleware to adapt it. Below is the corrected script:

```bash
#!/bin/bash

# Initialize default values
input_dir=""
testcase_dir=""
artifacts_dir=""

# Parse the command-line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --input_dir) input_dir="$2"; shift ;;
        --testcase_dir) testcase_dir="$2"; shift ;;
        --artifacts_dir) artifacts_dir="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Check if required arguments are provided
if [[ -z "$input_dir" || -z "$testcase_dir" || -z "$artifacts_dir" ]]; then
    echo "Error: Missing required arguments"
    echo "Usage: ./script.sh --input_dir <input_directory> --testcase_dir <testcase_dir> --artifacts_dir <artifacts_dir>"
    exit 1
fi

# Activate the virtual environment
source .venv/bin/activate

# Run the fuzzing command with the arguments
python ./examples/htmlparser/fuzz.py "$input_dir" --exact-artifact-path "$testcase_dir"
```

### How It Works

1. **Command-Line Parsing**:The script parses the required parameters (`--input_dir`, `--testcase_dir`, and `--artifacts_dir`) from the command line.
2. **Environment Setup**:Activates the virtual environment or any required setup for the fuzzer.
3. **Fuzzer Execution**:Runs the fuzzer with the provided parameters, ensuring compatibility with PinguBot's expectations.
4. **Output Handling**:

   - **`input_dir`**: The corpus directory containing input files for the fuzzer.
   - **`testcase_dir`**: The directory where test cases that cause crashes will be stored for reproduction.
   - **`artifacts_dir`**: The directory where miscellaneous output files, such as `.cov` files, will be stored in the backend system after the fuzzing session.

### Integration Steps

1. Place the middleware script in the fuzzer's directory.
2. Update the fuzzer's configuration to use the script as the executable.
3. Ensure the script and fuzzer are executable and properly configured.

## Important Notes

- **Corpus Synchronization**:The fuzzer must save generated test cases in the specified `testcase_dir` for synchronization with the backend.
- **Error Handling**:The fuzzer should handle errors gracefully and log meaningful messages for debugging.
- **Performance**:Optimize the fuzzer to generate test cases efficiently within the allocated time.
- **Coverage Data**:
  If possible, collect and upload coverage data to provide insights into the fuzzing session's effectiveness.

Refer to the `fuzz_task` implementation for additional details on how fuzzing sessions are managed and crashes are processed.
