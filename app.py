import streamlit as st
import pandas as pd
import os
from datetime import datetime
import qrcode
from streamlit_qrcode_scanner import qrcode_scanner

# ================= 配置区 =================
st.set_page_config(page_title="微型仓库管理系统 (Pro)", page_icon="📦", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

FILE_INVENTORY = os.path.join(DATA_DIR, "物品信息表.xlsx")
FILE_RECORDS = os.path.join(DATA_DIR, "流水记录表.xlsx")


# ================= 辅助函数 =================

def generate_qr_code(item_name):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(item_name)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    return img


@st.cache_data(ttl=60)
def load_data():
    try:
        df_inv = pd.read_excel(FILE_INVENTORY)
        # 确保有预警数量列
        if '预警数量' not in df_inv.columns:
            df_inv['预警数量'] = 10
    except FileNotFoundError:
        df_inv = pd.DataFrame(columns=['物品名称', '总库存', '单位', '备注', '二维码', '预警数量'])

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


# ================= 主程序 =================
df_inventory, df_records = load_data()

# ================= 导航菜单 =================
menu = st.sidebar.radio("导航菜单", ["📊 库存看板", "📥 入库管理", "📤 出库管理"])


# ================= 1. 库存看板 =================
if menu == "📊 库存看板":
    st.header("当前库存概览")
    st.caption("💡 提示：可在下方单独修改每个物品的预警数量。")

    # ---- 设置预警数量 ----
    st.subheader("🔧 设置物品预警数量")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        item_to_set = st.selectbox("选择要设置预警数量的物品", df_inventory['物品名称'].unique())
    with col2:
        new_threshold = st.number_input("预警数量", min_value=0, value=10, step=1)
    with col3:
        if st.button("✅ 更新预警"):
            if item_to_set:
                df_inventory.loc[df_inventory['物品名称'] == item_to_set, '预警数量'] = new_threshold
                save_inventory(df_inventory)
                st.success(f"已更新 {item_to_set} 的预警数量为 {new_threshold}")
                st.rerun()

    # ---- 搜索与展示 ----
    search_term = st.text_input("🔍 搜索物品名称")
    display_df = df_inventory.copy()
    if search_term:
        display_df = display_df[display_df['物品名称'].str.contains(search_term, na=False)]

    # 应用预警颜色
    def highlight_low_stock(row):
        if row['总库存'] <= row['预警数量']:
            return ['background-color: #FFCCCC'] * len(row)
        else:
            return [''] * len(row)

    styled_df = display_df.style.apply(highlight_low_stock, axis=1)
    st.dataframe(styled_df, width='stretch', hide_index=True)

    # ---- 二维码生成 ----
    st.subheader("生成/查看二维码")
    selected_item = st.selectbox("选择要生成二维码的物品", df_inventory['物品名称'].unique())
    if selected_item:
        qr_img = generate_qr_code(selected_item)
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(qr_img, caption=f"{selected_item} 的二维码", width=150)
        with col2:
            st.info("提示：打印此二维码贴在货架上。扫码时直接使用手机相机扫描即可。")


# ================= 2. 入库管理 =================
elif menu == "📥 入库管理":
    st.header("📥 物品入库")

    scan_mode = st.checkbox("📷 启用扫码模式 (使用相机扫描二维码)")

    if scan_mode:
        st.markdown("### 📸 请将摄像头对准二维码")
        # 修复：去掉 return_contents 参数
        scanned_code = qrcode_scanner(key='qr_scanner_in')

        if scanned_code:
            st.success(f"已识别物品：{scanned_code}")
            item_name = scanned_code
            is_new = item_name not in df_inventory['物品名称'].values

            if is_new:
                st.warning("⚠️ 这是一个新物品！请输入详细信息以完成首次入库。")
                new_qty = st.number_input("入库数量", min_value=1, value=1, key="new_in_qty")
                new_unit = st.text_input("单位 (如: 个/箱)", key="new_in_unit")
                operator = st.text_input("入库人", value="扫码入库", key="new_in_operator")

                if st.button("✅ 确认新物品入库"):
                    new_row = pd.DataFrame([{
                        '物品名称': item_name,
                        '总库存': new_qty,
                        '单位': new_unit,
                        '备注': '扫码自动新增',
                        '二维码': f'QR_{item_name}',
                        '预警数量': 10
                    }])
                    df_inventory = pd.concat([df_inventory, new_row], ignore_index=True)
                    save_inventory(df_inventory)

                    new_record = pd.DataFrame([{
                        '操作时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        '操作类型': '入库',
                        '物品名称': item_name,
                        '数量': new_qty,
                        '操作人': operator,
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
                operator = st.text_input("入库人", value="扫码入库", key="scan_in_operator")

                if st.button("✅ 确认入库"):
                    df_inventory.loc[df_inventory['物品名称'] == item_name, '总库存'] += add_qty
                    save_inventory(df_inventory)

                    new_record = pd.DataFrame([{
                        '操作时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        '操作类型': '入库',
                        '物品名称': item_name,
                        '数量': add_qty,
                        '操作人': operator,
                        '状态': '已完成',
                        '备注/原因': '扫码入库'
                    }])
                    df_records = pd.concat([df_records, new_record], ignore_index=True)
                    save_records(df_records)
                    st.success(f"成功入库 {add_qty} 个 {item_name}！")
                    st.balloons()
                    st.rerun()
        else:
            st.info("等待扫描二维码...")

    else:
        # 手动模式
        with st.form("manual_in_form"):
            if df_inventory.empty:
                st.warning("⚠️ 当前没有物品，请先扫码或手动添加一个新物品。")
                item_name = st.text_input("新物品名称 (如: M3螺丝)")
                unit = st.text_input("单位 (如: 个/箱)")
                qty = st.number_input("入库数量", min_value=1, value=1)
                operator = st.text_input("入库人", value="手动入库")
                if st.form_submit_button("提交入库"):
                    if not item_name:
                        st.error("请输入物品名称")
                    else:
                        new_row = pd.DataFrame([{
                            '物品名称': item_name,
                            '总库存': qty,
                            '单位': unit,
                            '备注': '手动新增',
                            '二维码': f'QR_{item_name}',
                            '预警数量': 10
                        }])
                        df_inventory = pd.concat([df_inventory, new_row], ignore_index=True)
                        save_inventory(df_inventory)
                        new_record = pd.DataFrame([{
                            '操作时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            '操作类型': '入库',
                            '物品名称': item_name,
                            '数量': qty,
                            '操作人': operator,
                            '状态': '已完成',
                            '备注/原因': '手动新增物品'
                        }])
                        df_records = pd.concat([df_records, new_record], ignore_index=True)
                        save_records(df_records)
                        st.success(f"成功添加并入库 {qty} 个 {item_name}！")
                        st.rerun()
            else:
                item_name = st.selectbox("选择物品", df_inventory['物品名称'].unique())
                quantity = st.number_input("入库数量", min_value=1, value=1)
                reason = st.text_input("备注/来源")
                operator = st.text_input("入库人", value="手动入库")
                submitted = st.form_submit_button("提交入库")
                if submitted:
                    df_inventory.loc[df_inventory['物品名称'] == item_name, '总库存'] += quantity
                    save_inventory(df_inventory)
                    new_record = pd.DataFrame([{
                        '操作时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        '操作类型': '入库',
                        '物品名称': item_name,
                        '数量': quantity,
                        '操作人': operator,
                        '状态': '已完成',
                        '备注/原因': reason
                    }])
                    df_records = pd.concat([df_records, new_record], ignore_index=True)
                    save_records(df_records)
                    st.success("入库成功！")
                    st.rerun()


# ================= 3. 出库管理 =================
elif menu == "📤 出库管理":
    st.header("📤 物品出库")

    scan_mode = st.checkbox("📷 启用扫码模式 (使用相机扫描二维码)", key="scan_out_check")

    if scan_mode:
        st.markdown("### 📸 请将摄像头对准二维码")
        # 修复：去掉 return_contents 参数
        scanned_code = qrcode_scanner(key='qr_scanner_out')

        if scanned_code:
            item_name = scanned_code
            if item_name in df_inventory['物品名称'].values:
                current_stock = int(df_inventory.loc[df_inventory['物品名称'] == item_name, '总库存'].values[0])
                st.success(f"已识别：{item_name} (当前库存: {current_stock})")

                out_qty = st.number_input("出库数量", min_value=1, max_value=current_stock, value=1, key="scan_out_qty")
                operator = st.text_input("出库人", value="扫码出库", key="scan_out_operator")

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
                            '操作人': operator,
                            '状态': '已完成',
                            '备注/原因': '扫码出库'
                        }])
                        df_records = pd.concat([df_records, new_record], ignore_index=True)
                        save_records(df_records)
                        st.success("出库成功！")
                        st.rerun()
            else:
                st.error(f"未找到物品：{item_name}，请先入库或检查二维码。")
        else:
            st.info("等待扫描二维码...")

    else:
        # 手动模式
        if df_inventory.empty:
            st.warning("⚠️ 当前没有物品，无法出库。请先入库。")
        else:
            with st.form("manual_out_form"):
                item_name = st.selectbox("选择物品", df_inventory['物品名称'].unique())
                current_stock = int(df_inventory.loc[df_inventory['物品名称'] == item_name, '总库存'].values[0])
                st.write(f"当前可用库存: **{current_stock}**")

                quantity = st.number_input("出库数量", min_value=1, max_value=current_stock, value=1)
                receiver = st.text_input("领用人")
                operator = st.text_input("出库人", value="手动出库")

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
                            '操作人': operator,
                            '状态': '已完成',
                            '备注/原因': f'{receiver} 领用' if receiver else '出库'
                        }])
                        df_records = pd.concat([df_records, new_record], ignore_index=True)
                        save_records(df_records)
                        st.success("出库成功！")
                        st.rerun()
