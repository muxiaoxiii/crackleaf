"""
pdf_unlocker.py

Provides a unified interface for unlocking password-protected PDF files
using PikePDF (structural removal) or PyPDF2 (page reconstruction).
"""

import pikepdf
from pikepdf import PasswordError as PikePasswordError
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.errors import DependencyError as PyPDF2DependencyError
from typing import Optional, TypedDict
from pathlib import Path
from typing import List
import logging
logger = logging.getLogger("crackleaf")
logging.basicConfig(level=logging.INFO)


class WrongPasswordError(Exception): pass

class UnlockResult(TypedDict):
    success: bool
    message: str
    method: str
    output_path: Optional[str]

# --- Strategy 1: Use PikePDF for high-fidelity structural unlocking ---
def _unlock_with_pikepdf(input_path: str, output_path: str, password: str) -> tuple[bool, str]:
    """
    Attempt to unlock a PDF using PikePDF by structurally removing encryption.

    Args:
        input_path (str): Path to the encrypted PDF.
        output_path (str): Destination for the unlocked PDF.
        password (str): Password for decryption.

    Returns:
        tuple[bool, str]: (success status, message)
    """
    try:
        # Attempt to open and save PDF without the encryption dictionary
        with pikepdf.open(input_path, password=password) as pdf:
            pdf.save(output_path)
        return True, "成功：已通过高保真模式移除限制。"
    except PikePasswordError:
        raise
    except Exception as e:
        logger.error(f"[PikePDF] 解密失败 ({input_path})，准备尝试备用方法。错误类型: {type(e).__name__}, 错误: {e}", exc_info=True)
        return False, f"PikePDF 失败: {e}"

# --- Strategy 2: Use PyPDF2 for fallback page-level reconstruction ---
def _unlock_with_pypdf2(input_path: str, output_path: str, password: str) -> tuple[bool, str]:
    """
    Attempt to unlock a PDF using PyPDF2 by reconstructing the content.

    Args:
        input_path (str): Path to the encrypted PDF.
        output_path (str): Destination for the rebuilt PDF.
        password (str): Password for decryption.

    Returns:
        tuple[bool, str]: (success status, message)
    """
    try:
        reader = PdfReader(input_path)
        if reader.is_encrypted:
            if not reader.decrypt(password):
                raise WrongPasswordError("密码错误")

        # Rebuild document without encryption
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        with open(output_path, "wb") as f:
            writer.write(f)
        
        return True, "成功：已通过备用模式移除限制（书签等可能丢失）。"
    except WrongPasswordError as e:
        raise
    except Exception as e:
        logger.error(f"[PyPDF2] 备用解密失败 ({input_path})。错误类型: {type(e).__name__}, 错误: {e}", exc_info=True)
        return False, f"PyPDF2 失败: {e}"

# --- Unified unlocking interface exposed to external callers ---
def unlock_pdf(input_path: str, output_path: str, password: str = '') -> UnlockResult:
    """
    Attempt to unlock a PDF using PikePDF (preferred) or PyPDF2 (fallback).
    Returns a dictionary describing the outcome.
    """
    if not output_path:
        return {
            "success": False,
            "message": "未指定输出路径。",
            "method": "失败",
            "output_path": None
        }
    try:
        # Preferred method: PikePDF for high-fidelity unlocking
        success, message = _unlock_with_pikepdf(input_path, output_path, password)
        if success:
            return {
                "success": True,
                "message": message,
                "method": "PikePDF (高保真)",
                "output_path": output_path
            }

        # If PikePDF fails (non-password), fallback to PyPDF2
        logger.info(f"[Unlocker] '{input_path}' 的高保真解密失败，尝试备用方法...")
        success, message = _unlock_with_pypdf2(input_path, output_path, password)
        if success:
            return {
                "success": True,
                "message": message,
                "method": "PyPDF2 (备用)",
                "output_path": output_path
            }

        # Both strategies failed
        return {
            "success": False,
            "message": f"所有解密方法均失败。最后错误: {message}",
            "method": "失败",
            "output_path": None
        }

    except (PikePasswordError, WrongPasswordError):
        msg = "密码错误或缺失。需要提供正确的密码才能打开此文件。"
        logger.warning(f"[Unlocker] '{input_path}' 解密失败: {msg}")
        return {
            "success": False,
            "message": msg,
            "method": "失败",
            "output_path": None
        }
    except Exception as e:
        logger.error(f"[Unlocker] '{input_path}' 解密过程中发生未知顶层错误: {type(e).__name__}: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"发生未知错误: {e}",
            "method": "失败",
            "output_path": None
        }

def batch_unlock_files(filepaths: List[str], password: str = '') -> List[UnlockResult]:
    """
    批量解锁 PDF 文件，自动生成输出路径。

    Args:
        filepaths (List[str]): 需要解锁的 PDF 文件路径列表。
        password (str, optional): 解锁密码。默认为空字符串。

    Returns:
        List[UnlockResult]: 每个文件的解锁结果。
    """
    results = []
    for path in filepaths:
        output_path = str(Path(path).with_stem(Path(path).stem + "_unlocked"))
        result = unlock_pdf(path, output_path, password)
        results.append(result)
    return results