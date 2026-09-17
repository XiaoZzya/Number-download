from __future__ import annotations

import qrcode


DONATION_TARGETS = (
    ("微信支付", "https://payapp.wechatpay.cn/sjt/qr/AQEQ9PnYyuHotIDyr71jOuTs"),
    ("支付宝", "https://qr.alipay.com/tsx19783zphnbqnd04xkcec"),
)


def _ascii_qr(value: str) -> str:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2)
    qr.add_data(value)
    qr.make(fit=True)
    return "\n".join("".join("##" if cell else "  " for cell in row) for row in qr.get_matrix())


def show_donation() -> None:
    print("感谢支持 Number download / ND！\n")
    for label, value in DONATION_TARGETS:
        print(f"=== {label} ===")
        print(_ascii_qr(value))
        print(f"链接：{value}\n")


if __name__ == "__main__":
    show_donation()
