"""The error code registry and APIError -- moved here from app.api.errors
(Tier 2 #5) because services raising APIError directly is exactly what
they've always done, but `from app.api.errors import ...` from a service
violates the api -> services -> repositories -> db layering both docs
commit to: services must never import from api. import-linter caught
this on its very first run, which is the whole point of adding it.

app/api/errors.py keeps the genuinely HTTP-specific half: the envelope
shape and the FastAPI exception handlers that turn an APIError raised
anywhere below into a response. This module -- core, sitting below both
api and services -- is what both of them are allowed to depend on.

This table is a contract with the mobile client as much as an internal
reference (backend-plan/07 §4). Adding a code without also adding its
message pair below ships an untranslated error, so new codes belong in
a reviewed change, not a one-off raise somewhere in a service.

Additions beyond the original registry are called out at their entry
below -- same kind of gap as the missing refresh_tokens table each time:
a flow the plan already committed to needed a code it never defined,
fixed by naming it here, not working around it silently.

**Bilingual error messages (product decision, revising architecture
§10's original "server never returns display text" rule):** every error
response now carries `message_en`/`message_ar` alongside the machine
`code`, and the client picks by system language rather than maintaining
its own translation table. `code` stays -- the client still needs it to
branch on behavior (e.g. auth.token_expired -> refresh), only the
*display text* moved server-side. Messages are deliberately generic per
code, not interpolated with `params` (a param like `field: "amount_minor"`
isn't natural-language material without its own translation, which
would multiply scope well beyond what a generic sentence needs to say).

The Arabic strings below are a first-pass machine draft, not reviewed
copy -- architecture §10 already flags that Arabic wording needs review
by a native speaker on the client's side before release, same as every
other user-facing string in the product. Treat `ERROR_MESSAGES`'s `ar`
side as placeholder text to swap for reviewed copy, not finished
translation.
"""

from __future__ import annotations

ERROR_STATUS: dict[str, int] = {
    "auth.invalid_credentials": 401,
    "auth.email_taken": 409,
    "auth.token_expired": 401,
    "auth.token_invalid": 401,
    "auth.weak_password": 422,
    "auth.current_password_incorrect": 422,  # addition: PATCH /me/password's current_password check
    "balance.as_of_in_future": 422,
    "balance.as_of_too_old": 422,
    "balance.negative_not_allowed": 422,
    "validation.required": 422,
    "validation.invalid": 422,
    "transaction.amount_not_positive": 422,
    "transaction.end_before_start": 422,
    "transaction.one_time_has_end_date": 422,
    "transaction.direction_immutable": 422,
    "scenario.base_immutable": 409,
    "scenario.name_taken": 409,
    "scenario.archived": 409,  # rejected as a compare operand or a duplicate source
    "scenario.not_archived": 409,  # unarchive attempted on a scenario that isn't archived
    "overlay.target_not_in_base": 422,
    "overlay.already_exists": 409,
    "overlay.scenario_is_base": 422,  # addition: overlays can't target the Base scenario itself
    "category.in_use": 409,  # addition: can't delete a user category still referenced
    "compare.same_scenario": 422,
    "forecast.invalid_horizon": 422,
    "resource.not_found": 404,
    "rate_limited": 429,
    "internal": 500,
}

# (english, arabic) -- see this module's docstring: generic per code, not
# interpolated with params, and the Arabic side is an unreviewed first draft.
ERROR_MESSAGES: dict[str, tuple[str, str]] = {
    "auth.invalid_credentials": (
        "The email or password you entered is incorrect.",
        "البريد الإلكتروني أو كلمة المرور التي أدخلتها غير صحيحة.",
    ),
    "auth.email_taken": (
        "An account with this email already exists.",
        "يوجد حساب بهذا البريد الإلكتروني بالفعل.",
    ),
    "auth.token_expired": (
        "Your session has expired. Please sign in again.",
        "انتهت صلاحية جلستك. يرجى تسجيل الدخول مرة أخرى.",
    ),
    "auth.token_invalid": (
        "Your session is no longer valid. Please sign in again.",
        "جلستك لم تعد صالحة. يرجى تسجيل الدخول مرة أخرى.",
    ),
    "auth.weak_password": (
        "Your password doesn't meet the minimum security requirements.",
        "كلمة المرور لا تفي بالحد الأدنى من متطلبات الأمان.",
    ),
    "auth.current_password_incorrect": (
        "Your current password is incorrect.",
        "كلمة المرور الحالية غير صحيحة.",
    ),
    "balance.as_of_in_future": (
        "The date you entered can't be in the future.",
        "لا يمكن أن يكون التاريخ الذي أدخلته في المستقبل.",
    ),
    "balance.negative_not_allowed": (
        "Current Cash Balance can't be negative.",
        "لا يمكن أن يكون رصيدك النقدي الحالي سالبًا.",
    ),
    "balance.as_of_too_old": (
        "The date you entered is too far in the past.",
        "التاريخ الذي أدخلته قديم جدًا.",
    ),
    "validation.required": (
        "This field is required.",
        "هذا الحقل مطلوب.",
    ),
    "validation.invalid": (
        "This field isn't valid.",
        "هذا الحقل غير صالح.",
    ),
    "transaction.amount_not_positive": (
        "The amount must be greater than zero.",
        "يجب أن يكون المبلغ أكبر من صفر.",
    ),
    "transaction.end_before_start": (
        "The end date can't be before the start date.",
        "لا يمكن أن يكون تاريخ الانتهاء قبل تاريخ البدء.",
    ),
    "transaction.one_time_has_end_date": (
        "A one-time item can't have an end date.",
        "لا يمكن أن يكون للعنصر لمرة واحدة تاريخ انتهاء.",
    ),
    "transaction.direction_immutable": (
        "Income and expense can't be changed after creation.",
        "لا يمكن تغيير نوع الدخل أو المصروف بعد الإنشاء.",
    ),
    "scenario.base_immutable": (
        "Your Base Plan can't be deleted or archived.",
        "لا يمكن حذف أو أرشفة خطتك الأساسية.",
    ),
    "scenario.name_taken": (
        "You already have a plan with this name.",
        "لديك بالفعل خطة بهذا الاسم.",
    ),
    "scenario.archived": (
        "This plan is archived. Restore it first.",
        "هذه الخطة مؤرشفة. يرجى استعادتها أولاً.",
    ),
    "scenario.not_archived": (
        "This plan isn't archived.",
        "هذه الخطة غير مؤرشفة.",
    ),
    "overlay.target_not_in_base": (
        "This item doesn't exist in your Base Plan.",
        "هذا العنصر غير موجود في خطتك الأساسية.",
    ),
    "overlay.already_exists": (
        "This item has already been changed in this plan.",
        "تم تغيير هذا العنصر بالفعل في هذه الخطة.",
    ),
    "overlay.scenario_is_base": (
        "This action isn't available on your Base Plan.",
        "هذا الإجراء غير متاح في خطتك الأساسية.",
    ),
    "category.in_use": (
        "This category is being used and can't be deleted.",
        "هذه الفئة مستخدمة حاليًا ولا يمكن حذفها.",
    ),
    "compare.same_scenario": (
        "Choose two different plans to compare.",
        "اختر خطتين مختلفتين للمقارنة.",
    ),
    "forecast.invalid_horizon": (
        "The selected time period isn't valid.",
        "الفترة الزمنية المحددة غير صالحة.",
    ),
    "resource.not_found": (
        "We couldn't find what you're looking for.",
        "تعذر العثور على ما تبحث عنه.",
    ),
    "rate_limited": (
        "Too many attempts. Please try again in a moment.",
        "عدد كبير جدًا من المحاولات. يرجى المحاولة مرة أخرى بعد قليل.",
    ),
    "internal": (
        "Something went wrong on our end. Please try again.",
        "حدث خطأ ما من جانبنا. يرجى المحاولة مرة أخرى.",
    ),
}

if ERROR_MESSAGES.keys() != ERROR_STATUS.keys():
    # Fails at import time, not at whatever request first hits the gap --
    # a code with a status but no message pair (or vice versa) is exactly
    # the "gap fixed by naming it here" pattern this module's docstring
    # already warns about, mechanised instead of trusted to review.
    missing = ERROR_STATUS.keys() - ERROR_MESSAGES.keys()
    extra = ERROR_MESSAGES.keys() - ERROR_STATUS.keys()
    raise RuntimeError(
        f"ERROR_MESSAGES out of sync with ERROR_STATUS -- missing: {missing or None}, "
        f"extra: {extra or None}"
    )


class APIError(Exception):
    """Raise this from a service or router; the code's HTTP status is
    looked up from the registry above so callers never have to repeat it
    (and can't accidentally pair a code with the wrong status)."""

    def __init__(self, code: str, params: dict | None = None) -> None:
        if code not in ERROR_STATUS:
            raise ValueError(f"unregistered error code: {code!r}")
        self.code = code
        self.status_code = ERROR_STATUS[code]
        self.params = params or {}
        super().__init__(code)
