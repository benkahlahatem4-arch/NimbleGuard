"""نقطة تشغيل رسومية لـ NimbleGuard بلا نافذة أوامر في Windows."""

from __future__ import annotations

import sys


def show_startup_error(message: str) -> None:
    """عرض الخطأ في نافذة رسومية كي لا يحتاج المستخدم إلى قراءة شاشة أوامر."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror("NimbleGuard", message, parent=root)
        root.destroy()
    except Exception:
        # لا نطبع أي أسرار أو تفاصيل حساسة عند فشل واجهة النظام نفسها.
        pass


try:
    from nimbleguard import NimbleGuardApp, Storage
except SystemExit as error:
    show_startup_error(str(error))
    sys.exit(1)
except Exception as error:
    show_startup_error(f"تعذر تشغيل NimbleGuard بأمان:\n{error}")
    sys.exit(1)


if __name__ == "__main__":
    try:
        Storage.ensure()
        app = NimbleGuardApp()
        app.mainloop()
    except Exception as error:
        show_startup_error(f"حدث خطأ غير متوقع أثناء التشغيل:\n{error}")
        sys.exit(1)
