"""文章作成AIの呼び出し（Gemini / ChatGPT(OpenAI) / Claude(Anthropic) を切り替え可能）。

config.json の "ai_provider" で使うAIを選ぶ:
  "gemini"  … Google Gemini（無料枠あり）      キー: GEMINI_API_KEY
  "openai"  … ChatGPT（OpenAI API・従量課金）  キー: OPENAI_API_KEY
  "claude"  … Claude（Anthropic API・従量課金） キー: ANTHROPIC_API_KEY
どのAIでも「プロンプト(+商品画像)を送り、JSONを受け取る」という同じ使い方になる。


違い:
- 失敗時に SystemExit ではなく GeminiError を投げる（1商品の失敗で全体を止めないため）
- 画像(inline_data)を添付できる（AIに商品画像の内容を確認させ、画像の選定・alt・説明文に使う）
- 呼び出し間隔と1回の実行あたりの上限回数を守る（無料枠のレート制限対策）
"""

import json
import os
import re
import time

import requests

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]


def set_models(main: str = None, fallbacks: list = None) -> None:
    """config.json の gemini_model / gemini_fallback_models で使うモデルを変えられる（Googleがモデル名を変えたとき用）。"""
    global GEMINI_MODEL, GEMINI_FALLBACK_MODELS
    if main and not os.getenv("GEMINI_MODEL"):
        GEMINI_MODEL = main
    if fallbacks:
        GEMINI_FALLBACK_MODELS = list(fallbacks)


class GeminiError(Exception):
    pass


AIError = GeminiError


class GeminiQuotaExceeded(GeminiError):
    """1回の実行で使える呼び出し回数を使い切った / 日次上限に達した。"""


_state = {"calls": 0, "last": 0.0, "interval": 7.0, "max_calls": 120}


_provider = {"name": "gemini", "openai_model": "gpt-6-luna", "claude_model": "claude-haiku-4-5-20251001"}
PROVIDER_LABEL = {"gemini": "Gemini", "openai": "ChatGPT", "claude": "Claude"}


def set_provider(config: dict) -> str:
    """config.json から使うAIを設定する。戻り値は表示用の名前。"""
    name = (os.getenv("AI_PROVIDER") or config.get("ai_provider") or "gemini").strip().lower()
    name = {"chatgpt": "openai", "gpt": "openai", "anthropic": "claude"}.get(name, name)
    if name not in PROVIDER_LABEL:
        raise GeminiError(f"config.json の ai_provider が不正です: {name}（gemini / openai / claude のどれか）")
    _provider["name"] = name
    _provider["openai_model"] = config.get("openai_model") or _provider["openai_model"]
    _provider["claude_model"] = config.get("claude_model") or _provider["claude_model"]
    if name != "gemini" and config.get("paid_ai_interval_sec") is not None:
        _state["interval"] = float(config["paid_ai_interval_sec"])
    return label()


def label() -> str:
    return PROVIDER_LABEL.get(_provider["name"], "AI")


def _parse_json_text(text: str) -> dict:
    """AIの返答からJSON部分を取り出す（```json ～ ``` で囲まれていても読めるように）。"""
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    if not t.startswith("{"):
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            t = t[i:j + 1]
    return json.loads(t)


def _wait_interval():
    gap = _state["interval"] - (time.time() - _state["last"])
    if gap > 0:
        time.sleep(gap)
    _state["last"] = time.time()


def _call_openai(prompt: str, images: list, temperature: float) -> dict:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise GeminiError("OPENAI_API_KEY が設定されていません")
    content = [{"type": "text", "text": prompt + "\n\n必ずJSONオブジェクトだけを出力してください。"}]
    for img in images or []:
        if img:
            content.append({"type": "image_url", "image_url": {"url": f"data:{img['mime_type']};base64,{img['data']}"}})
    body = {"model": _provider["openai_model"], "messages": [{"role": "user", "content": content}],
            "response_format": {"type": "json_object"}, "temperature": temperature}
    return _post_with_retry("https://api.openai.com/v1/chat/completions", {"Authorization": f"Bearer {key}"}, body,
                            lambda b: b["choices"][0]["message"]["content"], "openai")


def _call_claude(prompt: str, images: list, temperature: float) -> dict:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise GeminiError("ANTHROPIC_API_KEY が設定されていません")
    content = []
    for img in images or []:
        if img:
            content.append({"type": "image", "source": {"type": "base64", "media_type": img["mime_type"], "data": img["data"]}})
    content.append({"type": "text", "text": prompt + "\n\n説明や前置きは書かず、JSONオブジェクトだけを出力してください。"})
    body = {"model": _provider["claude_model"], "max_tokens": 8000, "temperature": min(max(temperature, 0), 1),
            "messages": [{"role": "user", "content": content}]}
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    return _post_with_retry("https://api.anthropic.com/v1/messages", headers, body,
                            lambda b: "".join(x.get("text", "") for x in b.get("content", []) if x.get("type") == "text"), "claude")


def _post_with_retry(url, headers, body, extract, kind) -> dict:
    """有料API(ChatGPT/Claude)の呼び出し。混雑(429/5xx)は待って再試行、残高不足は分かりやすいエラーにする。"""
    if _state["calls"] >= _state["max_calls"]:
        raise GeminiQuotaExceeded("今回の実行で使えるAI呼び出し回数の上限に達しました")
    wait, last = 5, ""
    for attempt in range(5):
        _wait_interval()
        try:
            r = requests.post(url, headers={**headers, "Content-Type": "application/json"}, json=body, timeout=180)
        except requests.RequestException as e:
            last = f"通信エラー: {type(e).__name__}"
            time.sleep(wait)
            wait = min(wait * 2, 60)
            continue
        if r.status_code == 200:
            try:
                result = _parse_json_text(extract(r.json()))
                _state["calls"] += 1
                return result
            except (KeyError, IndexError, ValueError, TypeError) as e:
                last = f"応答の解析に失敗: {type(e).__name__}"
                continue
        text = r.text[:400]
        last = f"[{PROVIDER_LABEL[kind]}] HTTP {r.status_code}"
        if r.status_code == 400 and kind == "openai":
            # モデルによっては temperature や JSONモード指定を受け付けないので外して再試行
            changed = False
            for k in ("temperature", "response_format"):
                if k in text and k in body:
                    body.pop(k)
                    changed = True
            if changed:
                continue
        if r.status_code in (401, 403):
            raise GeminiError(f"{last}: APIキーが正しくない可能性があります")
        if r.status_code == 404:
            raise GeminiError(f"{last}: モデル名が見つかりません（config.json の {kind}_model を確認）")
        if r.status_code == 429 and ("insufficient_quota" in text or "credit balance" in text.lower() or "billing" in text.lower()):
            raise GeminiQuotaExceeded(f"{last}: 残高（クレジット）が不足しています。管理画面でチャージしてください")
        if r.status_code in (429, 500, 502, 503, 529):
            print(f"    {last} → 待機して再試行", flush=True)
            time.sleep(wait)
            wait = min(wait * 2, 60)
            continue
        raise GeminiError(f"{last}: {text[:160]}")
    raise GeminiError(f"AIの呼び出しに失敗しました: {last}")


def configure(interval: float, max_calls: int) -> None:
    _state["interval"] = interval
    _state["max_calls"] = max_calls


def calls_used() -> int:
    return _state["calls"]


def _url(model):
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def call(prompt: str, images: list = None, temperature: float = 0.8, mock=None) -> dict:
    """プロンプト(+画像)を送り、JSONをdictで返す。"""
    if os.getenv("RAKUTEN_LP_MOCK") == "1":
        if mock is None:
            raise GeminiError("モックが指定されていません")
        _state["calls"] += 1
        return mock()

    if _provider["name"] == "openai":
        return _call_openai(prompt, images, temperature)
    if _provider["name"] == "claude":
        return _call_claude(prompt, images, temperature)

    # LP専用のキー(GEMINI_API_KEY_LP)があればそちらを使う（Threads自動投稿の無料枠を食い合わないため）
    key = os.getenv("GEMINI_API_KEY_LP") or os.getenv("GEMINI_API_KEY")
    if not key:
        raise GeminiError("GEMINI_API_KEY が設定されていません")
    if _state["calls"] >= _state["max_calls"]:
        raise GeminiQuotaExceeded("今回の実行で使えるGemini呼び出し回数の上限に達しました")

    parts = [{"text": prompt}]
    for img in images or []:
        if img:
            parts.append({"inline_data": img})
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }

    models = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]
    last_error = ""
    quota_hits = 0
    for model in models:
        wait = 5
        for attempt in range(3):
            gap = _state["interval"] - (time.time() - _state["last"])
            if gap > 0:
                time.sleep(gap)
            _state["last"] = time.time()
            try:
                r = requests.post(_url(model), params={"key": key}, json=payload, timeout=120)
            except requests.RequestException as e:
                last_error = f"通信エラー: {type(e).__name__}"
                time.sleep(wait)
                wait = min(wait * 2, 60)
                continue
            if r.status_code == 200:
                try:
                    body = r.json()
                    text = body["candidates"][0]["content"]["parts"][0]["text"]
                    result = json.loads(text)
                    _state["calls"] += 1  # 成功した呼び出しだけ数える
                    return result
                except (KeyError, IndexError, ValueError) as e:
                    last_error = f"応答の解析に失敗: {type(e).__name__}"
                    print(f"    Gemini [{model}] {last_error} → 再試行", flush=True)
                    continue
            last_error = f"[{model}] HTTP {r.status_code}"
            print(f"    Gemini {last_error} → 待機して再試行", flush=True)
            if r.status_code == 429:
                quota_hits += 1
                if "PerDay" in r.text or "per day" in r.text.lower():
                    break  # このモデルの日次上限。次のモデルへ
            if r.status_code in (429, 500, 503):
                # Geminiが「何秒後に再試行してよいか」を返している場合はそれに従う（無駄な再試行を減らす）
                m = re.search(r'"retryDelay"\s*:\s*"(\d+)', r.text)
                delay = min(int(m.group(1)) + 1, 90) if m else wait
                time.sleep(delay)
                wait = min(wait * 2, 60)
                continue
            raise GeminiError(last_error)
    if quota_hits >= len(models):
        raise GeminiQuotaExceeded("Geminiの利用上限に達しました（翌日に持ち越し）")
    raise GeminiError(f"Gemini呼び出しに失敗しました: {last_error}")
