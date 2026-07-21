import streamlit as st
import pandas as pd
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import qrcode
from PIL import Image
import io
import sys

# ================= 配置区 =================
st.set_page_config(page_title="微型仓库管理系统 (Pro)", page_icon="📦", layout="wide")

# 使用相对路径，自动在当前目录下创建 data 文件夹
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

FILE_INVENTORY = os.path.join(DATA_DIR, "物品信息表.xlsx")
FILE_RECORDS = os.path.join(DATA_DIR, "流水记录表.xlsx")

# 从 st.secrets 读取邮箱配置（需在 Streamlit Cloud 后台设置）
# 如果未配置，则邮件功能会提示错误
EMAIL_SENDER = st.secrets.get("email", {}).get("sender", "")
EMAIL_PASSWORD = st.secrets.get("email", {}).get("password", "")
EMAIL_RECEIVER = st.secrets.get("email", {}).get("receiver", "")


# ================= 辅助函数 =================

def generate_qr_code(item_name):
    """生成二维码并返回内存中的图片对象"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(item_name)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    return img


@st.cache_data(ttl=60)
def load_data():
    """加载数据，如果文件不存在则创建空表"""
    try:
        df_inv = pd.read_excel(FILE_INVENTORY)
        if '二维码' not in df_inv.columns:
            df_inv['二维码'] = ""
    except FileNotFoundError:
        df_inv = pd.DataFrame(columns=['物品名称', '总库存', '单位', '备注', '二维码'])

    try:
        df_rec = pd.read_excel(FILE_RECORDS)
    except FileNotFoundError:
        df_rec = pd.DataFrame(columns=['操作时间', '操作类型', '物品名称', '数量', '操作人', '状态', '备注/原因'])

    return df_inv, df_rec


def save_inventory(df):
    df.to_excel(FILE_INVENTORY, index=False)
    st.cache_data.clear()


def save_records(df):
    df.to_excel(FILE_RECORDS, index=False)
    st.cache_data.clear()


def send_email(subject, body):
    """使用 SMTP 发送邮件（需配置 st.secrets）"""
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        st.warning("邮件功能未配置，请设置 st.secrets 中的 email 信息。")
        st.code(f"邮件主题：{subject}\n邮件内容：{body}", language="text")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP('smtp.office365.com', 587)  # 如果使用 Outlook/Office 365
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        st.success("邮件已发送！")
    except Exception as e:
        st.error(f"邮件发送失败: {e}")


# ================= 主程序 =================
df_inventory, df_records = load_data()
menu = st.sidebar.radio("导航菜单", ["📊 库存看板", "📥 入库管理", "📤 出库管理", "🛒 采购申请"])

# --- 1. 库存看板 ---
if menu == "📊 库存看板":
    st.header("当前库存概览")

    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input("🔍 搜索物品名称")

    display_df = df_inventory.copy()
    if search_term:
        display_df = display_df[display_df['物品名称'].str.contains(search_term, na=False)]

    st.dataframe(display_df, width='stretch', hide_index=True)

    st.subheader("生成/查看二维码")
    selected_item = st.selectbox("选择要生成二维码的物品", df_inventory['物品名称'].unique())
    if selected_item:
        qr_img = generate_qr_code(selected_item)
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(qr_img, caption=f"{selected_item} 的二维码", width=150)
        with col2:
            st.info("提示：打印此二维码贴在货架上。扫码枪扫描后即可快速出入库。")

# --- 2. 入库管理 ---
elif menu == "📥 入库管理":
    st.header("📥 物品入库")

    scan_mode = st.checkbox("📷 启用扫码模式 (Scan Mode)")

    if scan_mode:
        st.markdown("### 👇 请在下方红框处点击，然后使用扫码枪扫描")
        scanned_code = st.text_input("扫码输入区", key="scan_in", label_visibility="collapsed",
                                     placeholder="等待扫描...")

        if scanned_code:
            st.success(f"已识别物品：{scanned_code}")
            item_name = scanned_code
            is_new = item_name not in df_inventory['物品名称'].values

            if is_new:
                st.warning("⚠️ 这是一个新物品！请输入详细信息以完成首次入库。")
                new_qty = st.number_input("入库数量", min_value=1, value=1, key="new_in_qty")
                new_unit = st.text_input("单位 (如: 个/箱)", key="new_in_unit")

                if st.button("✅ 确认新物品入库"):
                    new_row = pd.DataFrame([{
                        '物品名称': item_name,
                        '总库存': new_qty,
                        '单位': new_unit,
                        '备注': '扫码自动新增',
                        '二维码': f'QR_{item_name}'
                    }])
                    df_inventory = pd.concat([df_inventory, new_row], ignore_index=True)
                    save_inventory(df_inventory)

                    new_record = pd.DataFrame([{
                        '操作时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        '操作类型': '入库',
                        '物品名称': item_name,
                        '数量': new_qty,
                        '操作人': os.getlogin() if hasattr(os, 'getlogin') else "未知操作人",
                        '状态': '已完成',
                        '备注/原因': '扫码新物品入库'
                    }])
                    df_records = pd.concat([df_records, new_record], ignore_index=True)
                    save_records(df_records)
                    st.rerun()
            else:
                current_stock = int(df_inventory.loc[df_inventory['物品名称'] == item_name, '总库存'].values[0])
                st.write(f"当前库存: {current_stock}")
                add_qty = st.number_input("本次入库数量", min_value=1, value=1, key="add_in_qty")

                if st.button("✅ 确认入库"):
                    df_inventory.loc[df_inventory['物品名称'] == item_name, '总库存'] += add_qty
                    save_inventory(df_inventory)

                    new_record = pd.DataFrame([{
                        '操作时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        '操作类型': '入库',
                        '物品名称': item_name,
                        '数量': add_qty,
                        '操作人': os.getlogin() if hasattr(os, 'getlogin') else "未知操作人",
                        '状态': '已完成',
                        '备注/原因': '扫码入库'
                    }])
                    df_records = pd.concat([df_records, new_record], ignore_index=True)
                    save_records(df_records)
                    st.success(f"成功入库 {add_qty} 个 {item_name}！")
                    st.balloons()
                    st.rerun()

    else:
        with st.form("manual_in_form"):
            item_name = st.selectbox("选择物品", df_inventory['物品名称'].unique())
            quantity = st.number_input("入库数量", min_value=1, value=1)
            reason = st.text_input("备注/来源")

            submitted = st.form_submit_button("提交入库")
            if submitted:
                df_inventory.loc[df_inventory['物品名称'] == item_name, '总库存'] += quantity
                save_inventory(df_inventory)

                new_record = pd.DataFrame([{
                    '操作时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    '操作类型': '入库',
                    '物品名称': item_name,
                    '数量': quantity,
                    '操作人': os.getlogin() if hasattr(os, 'getlogin') else "未知操作人",
                    '状态': '已完成',
                    '备注/原因': reason
                }])
                df_records = pd.concat([df_records, new_record], ignore_index=True)
                save_records(df_records)
                st.success("入库成功！")
                st.rerun()

# --- 3. 出库管理 ---
elif menu == "📤 出库管理":
    st.header("📤 物品出库")

    scan_mode = st.checkbox("📷 启用扫码模式 (Scan Mode)", key="scan_out_check")

    if scan_mode:
        st.markdown("### 👇 请在下方红框处点击，然后使用扫码枪扫描")
        scanned_code = st.text_input("扫码输入区", key="scan_out", label_visibility="collapsed",
                                     placeholder="等待扫描...")

        if scanned_code:
            item_name = scanned_code
            if item_name in df_inventory['物品名称'].values:
                current_stock = int(df_inventory.loc[df_inventory['物品名称'] == item_name, '总库存'].values[0])
                st.success(f"已识别：{item_name} (当前库存: {current_stock})")

                out_qty = st.number_input("出库数量", min_value=1, max_value=current_stock, value=1, key="scan_out_qty")

                if st.button("✅ 确认出库"):
                    if out_qty > current_stock:
                        st.error("库存不足！")
                    else:
                        df_inventory.loc[df_inventory['物品名称'] == item_name, '总库存'] -= out_qty
                        save_inventory(df_inventory)

                        new_record = pd.DataFrame([{
                            '操作时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            '操作类型': '出库',
                            '物品名称': item_name,
                            '数量': out_qty,
                            '操作人': os.getlogin() if hasattr(os, 'getlogin') else "未知操作人",
                            '状态': '已完成',
                            '备注/原因': '扫码出库'
                        }])
                        df_records = pd.concat([df_records, new_record], ignore_index=True)
                        save_records(df_records)
                        st.success("出库成功！")
                        st.rerun()
            else:
                st.error(f"未找到物品：{item_name}，请先入库或检查条码。")
    else:
        with st.form("manual_out_form"):
            item_name = st.selectbox("选择物品", df_inventory['物品名称'].unique())
            current_stock = int(df_inventory.loc[df_inventory['物品名称'] == item_name, '总库存'].values[0])
            st.write(f"当前可用库存: **{current_stock}**")

            quantity = st.number_input("出库数量", min_value=1, max_value=current_stock, value=1)
            receiver = st.text_input("领用人")

            submitted = st.form_submit_button("提交出库")
            if submitted:
                if quantity > current_stock:
                    st.error("❌ 出库失败！库存不足。")
                else:
                    df_inventory.loc[df_inventory['物品名称'] == item_name, '总库存'] -= quantity
                    save_inventory(df_inventory)

                    new_record = pd.DataFrame([{
                        '操作时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        '操作类型': '出库',
                        '物品名称': item_name,
                        '数量': quantity,
                        '操作人': os.getlogin() if hasattr(os, 'getlogin') else "未知操作人",
                        '状态': '已完成',
                        '备注/原因': f'{receiver} 领用'
                    }])
                    df_records = pd.concat([df_records, new_record], ignore_index=True)
                    save_records(df_records)
                    st.success("出库成功！")
                    st.rerun()

# --- 4. 采购申请 ---
elif menu == "🛒 采购申请":
    st.header("提交新的采购申请")
    st.caption("填写以下信息后，系统将自动通过邮件发送审批申请。")

    with st.form("purchase_form"):
        approver_name = st.text_input("审批人姓名", value="申婷")
        item_name = st.text_input("物品名称", placeholder="例如：M3螺丝")
        quantity = st.number_input("申请数量", min_value=1, value=10)
        reason = st.text_area("申请原因", placeholder="例如：旧货架损坏，急需补充")

        submitted = st.form_submit_button("发送审批邮件")

        if submitted:
            if not item_name:
                st.error("⚠️ 物品名称不能为空！")
            else:
                email_subject = f"耗材申请 - {item_name}"
                current_user = os.getlogin() if hasattr(os, 'getlogin') else "未知操作人"
                email_body = f"""
                <h3>采购申请单</h3>
                <p><strong>申请人:</strong> {current_user}</p>
                <p><strong>审批人:</strong> {approver_name}</p>
                <table border="1" style="border-collapse: collapse; width: 100%;">
                    <tr style="background-color: #f2f2f2;">
                        <th style="padding: 8px;">物品名称</th>
                        <th style="padding: 8px;">申请数量</th>
                        <th style="padding: 8px;">申请原因</th>
                    </tr>
                    <tr>
                        <td style="padding: 8px;">{item_name}</td>
                        <td style="padding: 8px;">{quantity}</td>
                        <td style="padding: 8px;">{reason}</td>
                    </tr>
                </table>
                <br>
                <p>请审批。</p>
                """
                send_email(email_subject, email_body)
