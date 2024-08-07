

# Introduction

PinguBot is a fuzzing bot that allows you to automate your software testing. Fuzzy testing is a technique that injects random data into software to trigger unexpected behavior. PinguBot is designed to perform a specific set of tasks that cover various aspects of fuzzing, including:

1. **Analyze**: This task runs a manually uploaded test case against a job to see if it crashes. It helps to determine if a specific test case is viable for fuzz testing.
2. **Blame**: This task helps you identify the specific code that caused a problem detected during the fuzzing process. It helps to locate the root cause of an issue much more quickly than manual troubleshooting.
3. **Corpus pruning**: This task minimizes a corpus to the smallest size based on coverage (libFuzzer only).
4. **Fuzz**: This task runs a fuzzing session, which involves injecting random data into a piece of software to trigger unexpected behavior and find vulnerabilities.
5. **Impact analysis**: This task analyzes the potential impact of vulnerabilities detected during the fuzzing process, including the probability of execution, the severity, and the possible damage if the vulnerability is exploited.
6. **Minimization**: This task performs testcase minimization, which helps to reduce the time and resources required for testing.
7. **Train RNN generator**: This task involves training and retraining a machine learning model in the context of fuzzing.
8. **Progression testing**: This task checks if a test case still reproduces or if it's fixed. It helps to determine if previous bugs have been resolved or if new bugs have been introduced during a code change.
9. **Regression testing**: This task calculates the revision range in which a crash was introduced. This helps to determine the source of the issue and the changes that need to be reverted to fix the problem.
10. **Symbolize**: This task automatically generates a symbolic table for a piece of software, making it easier to analyze a bug or issue when it occurs.
11. **Unpack**: This task automatically unpacks a piece of software, making it easier to analyze its behavior and detect vulnerabilities.
12. **Upload reports**: This task automatically uploads the reports generated by the other tasks to a remote server for analysis and archival.
13. **Variant analysis**: This task allows you to run variants of a piece of software to see how it behaves in different scenarios, making it easier to detect and fix issues.

 By automating these tasks, you can save time and increase the efficiency of your software testing process."



# Deplyment & Usage

[Deployment](../../docs/deployment_instructions.md) and bot usage can be handled with the [Butler command line](../../docs/butler.md#Run-Bot-Command), which is part of the Pingucrew project. For added convenience, Pingubot also includes its own Butler command line that only includes the **run_bot** command. If you're exclusively using the PinguBot repository, you'll need to install the Python dependencies before running the Butler command line.

```bash
# create a local virtual enviroment
python -m venv .venv

# Activate the clean enviroment
source .venv/bin/activate

# install pip dependencies
pip install -r requirements.txt
```



Once all the dependencies are installed the bot can be exeuted using the following command:

```bash
python butler.py run_bot -c configs/test/bot test-bot
```

**Note**: that when running the `butlerrun_bot` command, a new working directory named `test-bot` is created. This directory includes the source code of the bot as well as all the files and folders from the original `bot_working_directory` folder. Additionally, the command includes the `--testing` flag, which sets the Python ROOT_DIR to the original `src/bot` folder. This allows developers to debug and modify code during the development process, without relying on the copied code. This feature is intended to provide convenience and improve the development experience.

# Bot Architecture

The bot internal details can be found in the [architecture document](docs/architecture.md).
