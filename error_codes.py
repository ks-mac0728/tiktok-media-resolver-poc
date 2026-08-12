"""
Error Code Taxonomy for Media Resolver PoC.

全 Resolver が返すエラーを統一コード体系にマッピングする。
8503 UI で日本語メッセージ表示に使用。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorSeverity(Enum):
    FATAL = "fatal"          # このURLでは絶対に取れない（削除済みなど）
    RETRYABLE = "retryable"  # 別方式なら取れる可能性あり
    CONFIG = "config"        # 設定不足（token未設定など）


class ErrorCategory(Enum):
    AUTH = "auth"                # 認証・ログイン関連
    AVAILABILITY = "availability"  # 動画の存在・公開状態
    NETWORK = "network"          # ネットワーク・WAF・レート制限
    FORMAT = "format"            # フォーマット・コーデック
    CONFIG = "config"            # 設定・環境
    UNKNOWN = "unknown"          # 分類不能


@dataclass(frozen=True)
class ErrorCode:
    code: str
    message_ja: str
    severity: ErrorSeverity
    category: ErrorCategory
    is_retryable: bool


# ---------------------------------------------------------------------------
# Error Code Registry
# ---------------------------------------------------------------------------

class ErrorCodes:
    # --- Auth ---
    LOGIN_REQUIRED = ErrorCode(
        "LOGIN_REQUIRED",
        "ログイン必須の投稿です。認証情報がないと取得できません。",
        ErrorSeverity.RETRYABLE,
        ErrorCategory.AUTH,
        is_retryable=True,
    )
    AUTH_FAILED = ErrorCode(
        "AUTH_FAILED",
        "認証に失敗しました。Cookie/Tokenが無効か期限切れです。",
        ErrorSeverity.RETRYABLE,
        ErrorCategory.AUTH,
        is_retryable=True,
    )
    CHALLENGE_REQUIRED = ErrorCode(
        "CHALLENGE_REQUIRED",
        "ロボット検証（CAPTCHA/Challenge）が要求されました。",
        ErrorSeverity.RETRYABLE,
        ErrorCategory.AUTH,
        is_retryable=True,
    )

    # --- Availability ---
    MEDIA_DELETED = ErrorCode(
        "MEDIA_DELETED",
        "動画が削除されています。",
        ErrorSeverity.FATAL,
        ErrorCategory.AVAILABILITY,
        is_retryable=False,
    )
    MEDIA_PRIVATE = ErrorCode(
        "MEDIA_PRIVATE",
        "非公開アカウントの投稿です。",
        ErrorSeverity.FATAL,
        ErrorCategory.AVAILABILITY,
        is_retryable=False,
    )
    MEDIA_NOT_FOUND = ErrorCode(
        "MEDIA_NOT_FOUND",
        "動画が見つかりませんでした（URL誤り、または地域制限の可能性）。",
        ErrorSeverity.FATAL,
        ErrorCategory.AVAILABILITY,
        is_retryable=False,
    )
    NOT_A_VIDEO = ErrorCode(
        "NOT_A_VIDEO",
        "この投稿は動画ではありません（画像のみの投稿）。",
        ErrorSeverity.FATAL,
        ErrorCategory.FORMAT,
        is_retryable=False,
    )
    EMPTY_MEDIA_RESPONSE = ErrorCode(
        "EMPTY_MEDIA_RESPONSE",
        "APIが空のレスポンスを返しました。ログイン必須の可能性があります。",
        ErrorSeverity.RETRYABLE,
        ErrorCategory.AVAILABILITY,
        is_retryable=True,
    )

    # --- Network ---
    RATE_LIMITED = ErrorCode(
        "RATE_LIMITED",
        "レート制限に達しました。時間を置いて再試行してください。",
        ErrorSeverity.RETRYABLE,
        ErrorCategory.NETWORK,
        is_retryable=True,
    )
    WAF_BLOCKED = ErrorCode(
        "WAF_BLOCKED",
        "WAF（Web Application Firewall）によりブロックされました。",
        ErrorSeverity.RETRYABLE,
        ErrorCategory.NETWORK,
        is_retryable=True,
    )
    NETWORK_TIMEOUT = ErrorCode(
        "NETWORK_TIMEOUT",
        "ネットワークタイムアウト。サーバーが応答しませんでした。",
        ErrorSeverity.RETRYABLE,
        ErrorCategory.NETWORK,
        is_retryable=True,
    )
    CDN_NOT_CAPTURED = ErrorCode(
        "CDN_NOT_CAPTURED",
        "CDNからの動画配信を検出できませんでした。",
        ErrorSeverity.RETRYABLE,
        ErrorCategory.NETWORK,
        is_retryable=True,
    )

    # --- Format ---
    FRAGMENTED_MP4 = ErrorCode(
        "FRAGMENTED_MP4",
        "fragmented MP4断片のみ取得。init segmentがなく単独再生不可。",
        ErrorSeverity.RETRYABLE,
        ErrorCategory.FORMAT,
        is_retryable=True,
    )
    UNSUPPORTED_FORMAT = ErrorCode(
        "UNSUPPORTED_FORMAT",
        "対応していない動画フォーマットです。",
        ErrorSeverity.FATAL,
        ErrorCategory.FORMAT,
        is_retryable=False,
    )

    # --- Config ---
    NOT_CONFIGURED = ErrorCode(
        "NOT_CONFIGURED",
        "Providerの設定が完了していません（API Token未設定など）。",
        ErrorSeverity.RETRYABLE,
        ErrorCategory.CONFIG,
        is_retryable=True,
    )
    RESOLVER_ERROR = ErrorCode(
        "RESOLVER_ERROR",
        "Resolver内部で予期せぬエラーが発生しました。",
        ErrorSeverity.RETRYABLE,
        ErrorCategory.UNKNOWN,
        is_retryable=True,
    )

    # --- Mapping table ---
    _BY_CODE: dict = {}

    @classmethod
    def by_code(cls, code: str) -> ErrorCode:
        if not cls._BY_CODE:
            cls._BY_CODE = {
                v.code: v
                for k, v in vars(cls).items()
                if isinstance(v, ErrorCode)
            }
        return cls._BY_CODE.get(code, cls.RESOLVER_ERROR)

    @classmethod
    def classify_error(cls, message: str, provider: str = "") -> ErrorCode:
        """エラーメッセージ文字列からErrorCodeを推測分類する"""
        msg_lower = message.lower()

        # yt-dlp の匿名アクセスは「not granting access / empty media response」の
        # 二値応答を返す。これはログイン必須・削除・非公開・画像のみ・存在しない
        # のいずれも区別できないため、EMPTY_MEDIA_RESPONSE に分類する。
        # この文言には "logged-in" が含まれ LOGIN_REQUIRED に誤分類されるため、
        # 必ず login/logged 判定より先にチェックする。
        if "not granting access" in msg_lower or "empty media response" in msg_lower:
            return cls.EMPTY_MEDIA_RESPONSE
        if "login" in msg_lower or "logged" in msg_lower:
            return cls.LOGIN_REQUIRED
        if "deleted" in msg_lower or "removed" in msg_lower:
            return cls.MEDIA_DELETED
        if "private" in msg_lower:
            return cls.MEDIA_PRIVATE
        if "not found" in msg_lower or "404" in msg_lower:
            return cls.MEDIA_NOT_FOUND
        if "not a video" in msg_lower or "no video" in msg_lower:
            return cls.NOT_A_VIDEO
        if "429" in msg_lower or "rate" in msg_lower:
            return cls.RATE_LIMITED
        if "timeout" in msg_lower:
            return cls.NETWORK_TIMEOUT
        if "waf" in msg_lower or "captcha" in msg_lower or "verify" in msg_lower:
            return cls.WAF_BLOCKED
        if "fragment" in msg_lower or "moof" in msg_lower or "fmp4" in msg_lower:
            return cls.FRAGMENTED_MP4
        if "token" in msg_lower or "未設定" in msg_lower:
            return cls.NOT_CONFIGURED
        if "captured=0" in msg_lower or "cdn" in msg_lower:
            return cls.CDN_NOT_CAPTURED

        return cls.RESOLVER_ERROR
