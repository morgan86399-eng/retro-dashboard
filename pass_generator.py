import io
import json
import zipfile
from PIL import Image, ImageDraw, ImageFont

def generate_vip_pass():
    pass_data = {
        "formatVersion": 1,
        "passTypeIdentifier": "pass.com.weiyo.retro",
        "serialNumber": "RETRO-4S-2026-001",
        "teamIdentifier": "WEIXTEAM01",
        "organizationName": "iPhone 4s 懷舊俱樂部",
        "description": "iPhone 4s 終極復古 VIP 黑卡",
        "logoText": "iPhone 4s VIP",
        "foregroundColor": "rgb(255, 255, 255)",
        "backgroundColor": "rgb(24, 28, 36)",
        "labelColor": "rgb(220, 180, 80)",
        "storeCard": {
            "primaryFields": [
                {
                    "key": "balance",
                    "label": "點數餘額",
                    "value": 999999,
                    "currencyCode": "TWD"
                }
            ],
            "secondaryFields": [
                {
                    "key": "holder",
                    "label": "持有人",
                    "value": "WeiYo"
                },
                {
                    "key": "tier",
                    "label": "會籍級別",
                    "value": "創始元老黑卡"
                }
            ],
            "auxiliaryFields": [
                {
                    "key": "device",
                    "label": "專屬設備",
                    "value": "iPhone 4s Retina"
                }
            ],
            "backFields": [
                {
                    "key": "about",
                    "label": "關於此卡",
                    "value": "恭喜您解鎖 iOS 6 Passbook 經典擬物化卡包！在右上角點擊垃圾桶可體驗經典紙條碎紙機特效。"
                },
                {
                    "key": "server",
                    "label": "雲端中繼節點",
                    "value": "http://192.168.0.185:8080"
                }
            ]
        },
        "barcode": {
            "message": "RETRO-IPHONE4S-VIP-WEIYO-2026",
            "format": "PKBarcodeFormatQR",
            "messageEncoding": "iso-8859-1"
        }
    }

    # Generate small icon (58x58)
    icon_img = Image.new("RGBA", (58, 58), (220, 180, 80, 255))
    draw = ImageDraw.Draw(icon_img)
    draw.rectangle([4, 4, 54, 54], fill=(30, 30, 30, 255), outline=(255, 215, 0, 255), width=2)
    
    icon_buf = io.BytesIO()
    icon_img.save(icon_buf, format="PNG")
    icon_bytes = icon_buf.getvalue()

    # Generate logo (200x50)
    logo_img = Image.new("RGBA", (200, 50), (0, 0, 0, 0))
    logo_buf = io.BytesIO()
    logo_img.save(logo_buf, format="PNG")
    logo_bytes = logo_buf.getvalue()

    # Build ZIP archive
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("pass.json", json.dumps(pass_data, ensure_ascii=False, indent=2).encode("utf-8"))
        z.writestr("icon.png", icon_bytes)
        z.writestr("icon@2x.png", icon_bytes)
        z.writestr("logo.png", logo_bytes)
        z.writestr("logo@2x.png", logo_bytes)
        
    return zip_buf.getvalue()
