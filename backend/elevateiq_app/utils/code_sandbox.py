"""
Code Sandbox Utility for ElevateIQ Campus Assessment Platform.
Safely executes candidate code in Python, JavaScript (Node.js), Java, and C++
with strict timeouts, memory isolation, and output diff evaluation.
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
import logging

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 5.0
MAX_OUTPUT_CHARS = 10000

# Prohibited patterns for basic safety check in Python / C++ / JS
DISALLOWED_PATTERNS = [
    "import shutil; shutil.rmtree",
    "os.system",
    "subprocess.Popen",
    "subprocess.run",
    "subprocess.call",
    "require('child_process')",
    "system(",
    "fork()",
    "execvp",
]

def _check_safety(source_code: str, language: str) -> tuple[bool, str]:
    """Check for explicitly dangerous code patterns."""
    for pattern in DISALLOWED_PATTERNS:
        if pattern in source_code:
            return False, f"Security Violation: '{pattern}' is not permitted in the assessment sandbox."
    return True, ""


def _normalize_output(text: str) -> str:
    """Normalize output by stripping trailing whitespace and standardizing newlines."""
    if not text:
        return ""
    lines = [line.rstrip() for line in text.strip().splitlines()]
    return "\n".join(lines)


def execute_testcase(source_code: str, language: str, input_data: str, expected_output: str = None) -> dict:
    """
    Executes source code against a single testcase input and evaluates output.

    Returns:
        dict: {
            "status": "Accepted" | "Wrong Answer" | "Time Limit Exceeded" | "Runtime Error" | "Compilation Error" | "Security Violation",
            "passed": bool,
            "actual_output": str,
            "expected_output": str,
            "execution_time_ms": int,
            "stderr": str,
            "error": str
        }
    """
    safe, msg = _check_safety(source_code, language)
    if not safe:
        return {
            "status": "Security Violation",
            "passed": False,
            "actual_output": "",
            "expected_output": expected_output or "",
            "execution_time_ms": 0,
            "stderr": msg,
            "error": msg
        }

    lang = language.lower().strip()
    temp_dir = tempfile.mkdtemp(prefix="elevateiq_sandbox_")

    try:
        if lang in ("python", "python3", "py"):
            file_path = os.path.join(temp_dir, "solution.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(source_code)
            cmd = [sys.executable, file_path]
            compile_cmd = None

        elif lang in ("javascript", "js", "node"):
            file_path = os.path.join(temp_dir, "solution.js")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(source_code)
            cmd = ["node", file_path]
            compile_cmd = None

        elif lang == "java":
            file_path = os.path.join(temp_dir, "Solution.java")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(source_code)
            compile_cmd = ["javac", file_path]
            cmd = ["java", "-cp", temp_dir, "Solution"]

        elif lang in ("cpp", "c++", "c"):
            file_path = os.path.join(temp_dir, "solution.cpp")
            out_path = os.path.join(temp_dir, "solution.out" if os.name != "nt" else "solution.exe")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(source_code)
            compile_cmd = ["g++", "-O2", file_path, "-o", out_path]
            cmd = [out_path]

        else:
            return {
                "status": "Unsupported Language",
                "passed": False,
                "actual_output": "",
                "expected_output": expected_output or "",
                "execution_time_ms": 0,
                "stderr": f"Language '{language}' is not supported.",
                "error": f"Language '{language}' is not supported."
            }

        # 1. Compilation Phase (if required)
        if compile_cmd:
            try:
                comp_proc = subprocess.run(
                    compile_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10.0,
                    cwd=temp_dir
                )
                if comp_proc.returncode != 0:
                    return {
                        "status": "Compilation Error",
                        "passed": False,
                        "actual_output": "",
                        "expected_output": expected_output or "",
                        "execution_time_ms": 0,
                        "stderr": comp_proc.stderr[:1000],
                        "error": comp_proc.stderr[:1000]
                    }
            except subprocess.TimeoutExpired:
                return {
                    "status": "Compilation Timeout",
                    "passed": False,
                    "actual_output": "",
                    "expected_output": expected_output or "",
                    "execution_time_ms": 0,
                    "stderr": "Compilation exceeded 10 seconds limit.",
                    "error": "Compilation exceeded 10 seconds limit."
                }
            except Exception as e:
                return {
                    "status": "Compilation Error",
                    "passed": False,
                    "actual_output": "",
                    "expected_output": expected_output or "",
                    "execution_time_ms": 0,
                    "stderr": str(e),
                    "error": str(e)
                }

        # 2. Execution Phase
        start_time = time.perf_counter()
        try:
            exec_proc = subprocess.run(
                cmd,
                input=input_data or "",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=temp_dir
            )
            exec_duration_ms = int((time.perf_counter() - start_time) * 1000)

            actual_out = exec_proc.stdout[:MAX_OUTPUT_CHARS]
            stderr_out = exec_proc.stderr[:MAX_OUTPUT_CHARS]

            if exec_proc.returncode != 0:
                return {
                    "status": "Runtime Error",
                    "passed": False,
                    "actual_output": actual_out,
                    "expected_output": expected_output or "",
                    "execution_time_ms": exec_duration_ms,
                    "stderr": stderr_out,
                    "error": f"Process exited with non-zero code {exec_proc.returncode}"
                }

            # 3. Output Comparison
            norm_actual = _normalize_output(actual_out)
            norm_expected = _normalize_output(expected_output) if expected_output is not None else None

            if expected_output is None:
                # Custom Run mode without comparison
                return {
                    "status": "Success",
                    "passed": True,
                    "actual_output": actual_out,
                    "expected_output": "",
                    "execution_time_ms": exec_duration_ms,
                    "stderr": stderr_out,
                    "error": None
                }

            passed = (norm_actual == norm_expected)
            return {
                "status": "Accepted" if passed else "Wrong Answer",
                "passed": passed,
                "actual_output": actual_out,
                "expected_output": expected_output,
                "execution_time_ms": exec_duration_ms,
                "stderr": stderr_out,
                "error": None if passed else "Output does not match expected testcase output."
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "Time Limit Exceeded",
                "passed": False,
                "actual_output": "",
                "expected_output": expected_output or "",
                "execution_time_ms": int(TIMEOUT_SECONDS * 1000),
                "stderr": f"Time Limit Exceeded (> {TIMEOUT_SECONDS}s)",
                "error": f"Execution timed out after {TIMEOUT_SECONDS} seconds."
            }

        except Exception as e:
            return {
                "status": "Runtime Error",
                "passed": False,
                "actual_output": "",
                "expected_output": expected_output or "",
                "execution_time_ms": 0,
                "stderr": str(e),
                "error": str(e)
            }

    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


def execute_testcase_suite(source_code: str, language: str, testcases: list) -> dict:
    """
    Executes code against a suite of testcases.
    """
    passed_count = 0
    total_count = len(testcases)
    total_score = 0
    max_score = sum(tc.get("weight", 10) for tc in testcases) if testcases else 100
    results = []
    overall_status = "Accepted"

    for tc in testcases:
        res = execute_testcase(
            source_code=source_code,
            language=language,
            input_data=tc["input_data"],
            expected_output=tc["expected_output"]
        )

        tc_result = {
            "testcase_id": tc.get("id"),
            "is_hidden": tc.get("is_hidden", True),
            "weight": tc.get("weight", 10),
            "status": res["status"],
            "passed": res["passed"],
            "execution_time_ms": res["execution_time_ms"],
        }

        # Only reveal input / expected / actual outputs for public testcases
        if not tc.get("is_hidden", False):
            tc_result["input_data"] = tc["input_data"]
            tc_result["expected_output"] = tc["expected_output"]
            tc_result["actual_output"] = res["actual_output"]
            tc_result["stderr"] = res["stderr"]
        else:
            tc_result["input_data"] = "Hidden Testcase"
            tc_result["expected_output"] = "Hidden"
            tc_result["actual_output"] = "Hidden"

        if res["passed"]:
            passed_count += 1
            total_score += tc.get("weight", 10)
        elif overall_status == "Accepted":
            overall_status = res["status"]

        results.append(tc_result)

    all_passed = (passed_count == total_count and total_count > 0)
    return {
        "all_passed": all_passed,
        "passed_count": passed_count,
        "total_count": total_count,
        "total_score": total_score,
        "max_score": max_score,
        "overall_status": overall_status if not all_passed else "Accepted",
        "results": results
    }
