"""Bilingual confirmation messages for action endpoints -- the success-side
counterpart to app.core.errors.ERROR_MESSAGES.

Scoped deliberately narrow (product decision): only the handful of
endpoints that return no resource body at all (they used to be a bare
204 No Content) get one of these. Endpoints that return the resource
they just created or changed (POST /scenarios, PATCH /transactions/{id},
...) do not -- the client already has everything it needs from the
returned data to compose its own contextual copy ("Added to Buy House"),
exactly as screen-flow §10 already specifies. Adding a message here to
every endpoint would be a far bigger, more invasive change (every schema
gains a field, every existing test asserting the current flat response
shape needs rewriting) for no real gain over what the client can already
do with data it has.

Since these endpoints no longer return an empty body, they're 200 OK,
not 204 -- a 204 response cannot carry content at all (RFC 7231).

Same caveat as ERROR_MESSAGES: the Arabic side is a first-pass machine
draft, not reviewed copy, and needs a native speaker's review before
release (architecture §10).
"""

from __future__ import annotations

# (english, arabic)
SUCCESS_MESSAGES: dict[str, tuple[str, str]] = {
    "auth.logged_out": (
        "You've been logged out.",
        "تم تسجيل خروجك.",
    ),
    # Deliberately neutral wording -- this endpoint always returns success
    # regardless of whether the email is registered, to avoid confirming
    # account existence (architecture §11 / rate-limit section).
    "auth.password_reset_requested": (
        "If an account exists for that email, we've sent a link to reset the password.",
        "إذا كان هناك حساب مرتبط بهذا البريد الإلكتروني، "
        "فقد أرسلنا رابطًا لإعادة تعيين كلمة المرور.",
    ),
    "auth.password_reset_confirmed": (
        "Your password has been changed.",
        "تم تغيير كلمة المرور الخاصة بك.",
    ),
    "transaction.deleted": (
        "Transaction deleted.",
        "تم حذف المعاملة.",
    ),
    "scenario.deleted": (
        "Plan deleted.",
        "تم حذف الخطة.",
    ),
    "category.deleted": (
        "Category deleted.",
        "تم حذف الفئة.",
    ),
    "overlay.deleted": (
        "Change reverted to Base.",
        "تمت إعادة التغيير إلى الخطة الأساسية.",
    ),
    "me.data_reset": (
        "Your data has been reset.",
        "تمت إعادة تعيين بياناتك.",
    ),
    "me.account_deleted": (
        "Your account has been deleted.",
        "تم حذف حسابك.",
    ),
}
