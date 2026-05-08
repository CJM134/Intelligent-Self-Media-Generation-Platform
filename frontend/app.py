import streamlit as st
import requests
import json
from datetime import datetime

st.set_page_config(page_title="Content Agent", layout="wide")

st.title("🚀 新媒体内容生成助手")

# API 地址：优先使用环境变量，否则使用默认值
import os
api_url = os.getenv("API_URL", "http://127.0.0.1:8000")

# 侧边栏配置
with st.sidebar:
    st.header("⚙️ 配置")
    st.info(f"API 地址: {api_url}")
    st.markdown("---")
    st.markdown("### 📖 使用说明")
    st.markdown("1. 输入原始内容\n2. 点击生成\n3. 查看多平台文案")

    # 定时任务快速状态
    st.markdown("---")
    st.markdown("### ⏰ 自动任务")
    try:
        task_resp = requests.get(f"{api_url}/api/scheduled-task/status", timeout=5)
        if task_resp.status_code == 200:
            is_running = task_resp.json()["is_running"]
            st.markdown(f"{'🟢 运行中' if is_running else '⏸️ 等待中'} 每2小时执行")
            if st.button("🔄 手动执行", key="manual_trigger", use_container_width=True):
                try:
                    trigger_resp = requests.post(
                        f"{api_url}/api/scheduled-task/trigger", timeout=5
                    )
                    if trigger_resp.status_code == 200:
                        st.success("任务已触发")
                        st.rerun()
                    else:
                        st.error("触发失败")
                except Exception as e:
                    st.error(f"错误: {str(e)}")
    except Exception:
        st.caption("无法获取任务状态")

    # Agent 技能展示
    st.markdown("---")
    st.markdown("### 🤖 Agent 技能")
    try:
        skills_resp = requests.get(f"{api_url}/api/agents/skills", timeout=5)
        if skills_resp.status_code == 200:
            agents_data = skills_resp.json().get("agents", [])
            for agent in agents_data:
                with st.expander(f"**{agent['name']}**"):
                    st.caption(agent.get("role", "")[:80])
                    for skill in agent.get("skills", []):
                        st.markdown(f"- **{skill['name']}**: {skill['description']}")
    except Exception:
        st.caption("无法加载技能信息")

# 主界面
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 生成文案", "🔥 热点跟踪", "📊 历史记录", "📈 数据分析与预测", "⏰ 定时任务"])

with tab1:
    st.subheader("输入原始内容")
    # 输入原始内容
    original_content = st.text_area(
        "请输入要转换的内容",
        height=150,
        placeholder="粘贴你的原始文案..."
    )

    # 行业选择
    industry = st.selectbox(
        "选择行业（可选）",
        ["", "科技", "美妆", "食品", "教育", "其他"]
    )

    # 生成按钮
    if st.button("✨ 生成多平台文案", use_container_width=True):
        # 调用 API 生成文案
        if not original_content.strip():
            st.error("请输入内容")
        else:
            with st.spinner("正在生成..."):
                try:
                    response = requests.post(
                        f"{api_url}/api/generate-content",
                        json={
                            "content": original_content,
                            "industry": industry if industry else None
                        },
                        timeout=120
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.success("生成成功！")

                        # 显示生成结果
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("### 小红书")
                            st.text_area(
                                "小红书文案",
                                value=data["results"]["xiaohongshu"],
                                height=200,
                                disabled=True,
                                label_visibility="collapsed"
                            )

                        with col2:
                            st.markdown("### 抖音")
                            st.text_area(
                                "抖音文案",
                                value=data["results"]["douyin"],
                                height=200,
                                disabled=True,
                                label_visibility="collapsed"
                            )

                        col3, col4 = st.columns(2)
                        with col3:
                            st.markdown("### 公众号")
                            st.text_area(
                                "公众号文案",
                                value=data["results"]["wechat"],
                                height=200,
                                disabled=True,
                                label_visibility="collapsed"
                            )

                        with col4:
                            st.markdown("### 微博")
                            st.text_area(
                                "微博文案",
                                value=data["results"]["weibo"],
                                height=200,
                                disabled=True,
                                label_visibility="collapsed"
                            )

                        # 显示 AI 配图
                        if data.get("image_url"):
                            st.markdown("---")
                            st.markdown("### 🖼️ AI 配图")
                            st.image(data["image_url"], use_container_width=True)

                    else:
                        st.error(f"生成失败: {response.text}")
                except Exception as e:
                    st.error(f"错误: {str(e)}")

with tab2:
    st.subheader("🔥 热点跟踪")

    # 平台选择和刷新按钮
    col1, col2 = st.columns([3, 1])
    with col1:
        platform_filter = st.selectbox(
            "选择平台",
            ["all", "douyin", "weibo", "xiaohongshu"],
            format_func=lambda x: {
                "all": "全部平台",
                "douyin": "抖音",
                "weibo": "微博",
                "xiaohongshu": "小红书"
            }[x]
        )

    with col2:
        if st.button("🔄 刷新热点", use_container_width=True):
            with st.spinner("正在获取最新热点..."):
                try:
                    response = requests.post(
                        f"{api_url}/api/hot-topics/refresh",
                        params={"platform": platform_filter},
                        timeout=30
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.success(f"✅ {data['message']}")
                        st.rerun()
                    else:
                        st.error("刷新失败")
                except Exception as e:
                    st.error(f"错误: {str(e)}")

    # 获取并显示热点列表
    try:
        response = requests.get(
            f"{api_url}/api/hot-topics",
            params={"platform": platform_filter, "limit": 20},
            timeout=10
        )

        if response.status_code == 200:
            topics = response.json()

            if not topics:
                st.info("暂无热点数据，请点击刷新按钮获取")
            else:
                st.markdown(f"### 共 {len(topics)} 条热点")

                # 显示热点列表
                for topic in topics:
                    with st.container():
                        col1, col2, col3 = st.columns([1, 6, 2])

                        with col1:
                            st.markdown(f"**#{topic['rank']}**")

                        with col2:
                            platform_emoji = {
                                "douyin": "🎵",
                                "weibo": "📱",
                                "xiaohongshu": "📕"
                            }
                            emoji = platform_emoji.get(topic['platform'], "🔥")
                            st.markdown(f"{emoji} **{topic['title']}**")
                            if topic.get('description'):
                                st.caption(topic['description'][:100] + "..." if len(topic['description']) > 100 else topic['description'])
                            if topic.get('tags'):
                                st.caption(f"🏷️ {topic['tags']}")

                        with col3:
                            if st.button("生成文案", key=f"gen_{topic['id']}", use_container_width=True):
                                with st.spinner("正在生成..."):
                                    try:
                                        gen_response = requests.post(
                                            f"{api_url}/api/generate-from-topic",
                                            params={"topic_id": topic['id']},
                                            timeout=120
                                        )
                                        if gen_response.status_code == 200:
                                            data = gen_response.json()
                                            st.session_state['generated_content'] = data['results']
                                            st.success("生成成功！")
                                        else:
                                            st.error("生成失败")
                                    except Exception as e:
                                        st.error(f"错误: {str(e)}")

                        st.divider()

                # 显示生成的内容
                if 'generated_content' in st.session_state:
                    st.markdown("### 📝 生成的文案")
                    results = st.session_state['generated_content']

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### 小红书")
                        st.text_area(
                            "小红书文案",
                            value=results.get("xiaohongshu", ""),
                            height=200,
                            disabled=True,
                            label_visibility="collapsed",
                            key="hot_xhs"
                        )

                    with col2:
                        st.markdown("#### 抖音")
                        st.text_area(
                            "抖音文案",
                            value=results.get("douyin", ""),
                            height=200,
                            disabled=True,
                            label_visibility="collapsed",
                            key="hot_dy"
                        )

                    col3, col4 = st.columns(2)
                    with col3:
                        st.markdown("#### 公众号")
                        st.text_area(
                            "公众号文案",
                            value=results.get("wechat", ""),
                            height=200,
                            disabled=True,
                            label_visibility="collapsed",
                            key="hot_wx"
                        )

                    with col4:
                        st.markdown("#### 微博")
                        st.text_area(
                            "微博文案",
                            value=results.get("weibo", ""),
                            height=200,
                            disabled=True,
                            label_visibility="collapsed",
                            key="hot_wb"
                        )
        else:
            st.error("获取热点失败")
    except Exception as e:
        st.error(f"错误: {str(e)}")

with tab3:
    st.subheader("历史记录")

    # 自动加载历史记录
    col_h1, col_h2 = st.columns([3, 1])
    with col_h2:
        refresh_clicked = st.button("🔄 刷新历史记录", use_container_width=True)

    # 始终获取历史（页面重载时也自动加载）
    try:
        resp = requests.get(f"{api_url}/api/history", timeout=10)
        if resp.status_code == 200:
            records = resp.json()["records"]
            st.info(f"共 {len(records)} 条记录" if records else "暂无历史记录")

            for record in records:
                created = record.get("created_at", "")[:19].replace("T", " ") if record.get("created_at") else "未知时间"
                original = record.get("original_content", "")
                preview = original[:80] + "..." if len(original) > 80 else original

                with st.expander(f"🕐 {created} | {preview}"):
                    st.markdown("**原始内容**")
                    st.text_area("原始内容", value=original, height=100,
                                 disabled=True, label_visibility="collapsed",
                                 key=f"orig_{record['id']}")

                    plat_col1, plat_col2 = st.columns(2)
                    with plat_col1:
                        st.markdown("**小红书文案**")
                        st.text_area("小红书", value=record.get("xiaohongshu_content", ""),
                                     height=150, disabled=True, label_visibility="collapsed",
                                     key=f"xhs_{record['id']}")
                        st.markdown("**公众号文案**")
                        st.text_area("公众号", value=record.get("wechat_content", ""),
                                     height=150, disabled=True, label_visibility="collapsed",
                                     key=f"wx_{record['id']}")

                    with plat_col2:
                        st.markdown("**抖音文案**")
                        st.text_area("抖音", value=record.get("douyin_content", ""),
                                     height=150, disabled=True, label_visibility="collapsed",
                                     key=f"dy_{record['id']}")
                        st.markdown("**微博文案**")
                        st.text_area("微博", value=record.get("weibo_content", ""),
                                     height=150, disabled=True, label_visibility="collapsed",
                                     key=f"wb_{record['id']}")

                    # 显示配图
                    if record.get("image_url"):
                        st.markdown("---")
                        st.markdown("**🖼️ AI 配图**")
                        st.image(record["image_url"], use_container_width=True)
        else:
            st.error("获取历史记录失败")
    except Exception as e:
        st.error(f"错误: {str(e)}")

with tab4:
    st.subheader("📈 热点数据分析与爆款预测")

    # ---- 概览卡片 ----
    st.markdown("### 平台概览")
    col_a1, col_a2, col_a3, col_a4 = st.columns(4)
    try:
        plat_resp = requests.get(f"{api_url}/api/analysis/platform-compare", timeout=10)
        if plat_resp.status_code == 200:
            plat_data = plat_resp.json()
            total_topics = sum(p["topic_count"] for p in plat_data)
            avg_heat_all = sum(p["avg_heat"] for p in plat_data) / max(len(plat_data), 1)
            max_heat_all = max((p["max_heat"] for p in plat_data), default=0)

            with col_a1:
                st.metric("总热点数", total_topics)
            with col_a2:
                st.metric("平台数", len(plat_data))
            with col_a3:
                st.metric("平均热度", f"{avg_heat_all:,.0f}")
            with col_a4:
                st.metric("最高热度", f"{max_heat_all:,.0f}")
    except Exception:
        st.info("暂无可分析数据，请先在热点跟踪页面刷新热点")

    # ---- 平台对比柱状图 ----
    st.markdown("---")
    st.markdown("### 平台数据对比")
    try:
        plat_resp = requests.get(f"{api_url}/api/analysis/platform-compare", timeout=10)
        if plat_resp.status_code == 200:
            plat_data = plat_resp.json()
            if plat_data:
                chart_df = {
                    "平台": [p["platform"] for p in plat_data],
                    "平均热度": [p["avg_heat"] for p in plat_data],
                    "总热度": [p["total_heat"] for p in plat_data],
                }
                st.bar_chart(chart_df, x="平台", y=["平均热度", "总热度"])
    except Exception:
        pass

    # ---- 分类统计 ----
    st.markdown("---")
    st.markdown("### 话题分类统计")
    try:
        cat_resp = requests.get(f"{api_url}/api/analysis/category-stats", timeout=10)
        if cat_resp.status_code == 200:
            cat_data = cat_resp.json()
            if cat_data:
                cat_df = {
                    "分类": [c["category"] for c in cat_data[:10]],
                    "话题数": [c["topic_count"] for c in cat_data[:10]],
                    "平均热度": [c["avg_heat"] for c in cat_data[:10]],
                }
                st.bar_chart(cat_df, x="分类", y=["话题数", "平均热度"])
    except Exception:
        pass

    # ---- 趋势话题 ----
    st.markdown("---")
    st.markdown("### 热度上升趋势")
    try:
        trend_resp = requests.get(
            f"{api_url}/api/analysis/trend",
            params={"hours": 24, "limit": 10},
            timeout=10
        )
        if trend_resp.status_code == 200:
            trend_data = trend_resp.json()
            if trend_data:
                trend_options = {t["title"]: t for t in trend_data}
                selected = st.selectbox(
                    "选择话题查看详细趋势",
                    options=list(trend_options.keys()),
                    format_func=lambda x: f"[{trend_options[x]['platform']}] {x[:30]}"
                )
                if selected:
                    t = trend_options[selected]
                    col_t1, col_t2, col_t3 = st.columns(3)
                    with col_t1:
                        st.metric("当前热度", f"{t['current_score']:,.0f}")
                    with col_t2:
                        delta = f"{t['heat_change']:+,.0f}"
                        st.metric("变化量", delta)
                    with col_t3:
                        st.metric("变化率",
                                  f"{t['heat_change_percent']:+.1f}%")

                    if t["trend_data"]:
                        trend_chart = {
                            "时间": [p["recorded_at"][11:19] for p in t["trend_data"]],
                            "热度": [p["heat_score"] for p in t["trend_data"]],
                        }
                        st.line_chart(trend_chart, x="时间", y="热度")
    except Exception:
        pass

    # ---- 高峰时段分析 ----
    st.markdown("---")
    st.markdown("### 各平台发布高峰时段")
    try:
        peak_resp = requests.get(f"{api_url}/api/analysis/peak-hours", timeout=10)
        if peak_resp.status_code == 200:
            peak_data = peak_resp.json()
            if peak_data:
                peak_cols = st.columns(len(peak_data))
                for i, (platform, info) in enumerate(peak_data.items()):
                    with peak_cols[i]:
                        hours_str = ", ".join(f"{h}:00" for h in info["suggested_hours"])
                        st.markdown(f"**{platform}**")
                        st.markdown(f"话题数: {info['topic_count']}")
                        st.markdown(f"建议时段: {hours_str}")
    except Exception:
        pass

    # ---- 爆款预测 ----
    st.markdown("---")
    st.markdown("### 🔥 爆款潜力预测")
    st.caption("输入内容标题和正文，AI 将基于当前热点数据预测爆款潜力")

    with st.form("predict_form"):
        pred_title = st.text_input(
            "内容标题 *",
            placeholder="输入标题（必填）",
            max_chars=100
        )
        pred_content = st.text_area(
            "内容正文（可选）",
            placeholder="输入正文内容...",
            height=100
        )
        pred_platform = st.selectbox(
            "目标平台",
            ["all", "douyin", "weibo", "xiaohongshu"],
            format_func=lambda x: {
                "all": "智能推荐", "douyin": "抖音",
                "weibo": "微博", "xiaohongshu": "小红书"
            }[x]
        )
        submitted = st.form_submit_button("🚀 开始预测", use_container_width=True)

    if submitted:
        if not pred_title.strip():
            st.error("请输入内容标题")
        else:
            with st.spinner("AI 正在分析爆款潜力..."):
                try:
                    resp = requests.post(
                        f"{api_url}/api/prediction/predict",
                        json={
                            "title": pred_title,
                            "content": pred_content,
                            "platform": pred_platform,
                        },
                        timeout=30
                    )
                    if resp.status_code == 200:
                        result = resp.json()

                        score = result["viral_score"]
                        st.markdown("#### 预测结果")

                        score_cols = st.columns([1, 2, 1])
                        with score_cols[0]:
                            color = "green" if score >= 70 else (
                                "orange" if score >= 40 else "red"
                            )
                            st.markdown(
                                f"<h1 style='color:{color}; text-align:center;'>"
                                f"{score}</h1>"
                                f"<p style='text-align:center;'>爆款潜力分</p>",
                                unsafe_allow_html=True
                            )

                        with score_cols[1]:
                            st.markdown(f"**置信度**: {result['confidence']}")
                            st.markdown(
                                f"**建议首发**: {result['suggested_platform']}"
                            )
                            st.markdown(
                                f"**建议时间**: {result['peak_hour']}:00"
                            )

                        with score_cols[2]:
                            st.markdown("##### 评分等级")
                            if score >= 70:
                                st.success("🔥 爆款潜力高")
                            elif score >= 40:
                                st.warning("💡 有一定潜力")
                            else:
                                st.info("📝 需优化")

                        if result.get("reasons"):
                            st.markdown("##### ✅ 优势分析")
                            for r in result["reasons"]:
                                st.markdown(f"- {r}")

                        if result.get("suggestions"):
                            st.markdown("##### 💡 优化建议")
                            for s in result["suggestions"]:
                                st.markdown(f"- {s}")

                        st.markdown("---")
                        st.markdown("##### 📊 参考：当前高热话题")
                        try:
                            ref_resp = requests.get(
                                f"{api_url}/api/hot-topics",
                                params={"limit": 5},
                                timeout=10
                            )
                            if ref_resp.status_code == 200:
                                ref_topics = ref_resp.json()
                                for t in ref_topics:
                                    emoji = {
                                        "douyin": "🎵", "weibo": "📱",
                                        "xiaohongshu": "📕"
                                    }.get(t["platform"], "🔥")
                                    st.markdown(
                                        f"{emoji} **{t['title']}** "
                                        f"— 热度 {t['heat_score']:,.0f}"
                                    )
                        except Exception:
                            pass
                    else:
                        st.error(f"预测失败: {resp.text}")
                except Exception as e:
                    st.error(f"请求错误: {str(e)}")

with tab5:
    st.subheader('⏰ 定时任务记录')
    st.caption('每2小时自动抓取抖音/微博各10条热点 → 生成4平台文案 → 预测下一个热点')

    col_h1, col_h2 = st.columns([3, 1])
    with col_h2:
        if st.button('🔄 手动触发任务', use_container_width=True):
            try:
                r = requests.post(f'{api_url}/api/scheduled-task/trigger', timeout=5)
                if r.status_code == 200:
                    st.success('任务已触发')
                    st.rerun()
                else:
                    st.error('触发失败')
            except Exception as e:
                st.error(f'错误: {str(e)}')

    # 当前状态卡片
    try:
        r = requests.get(f'{api_url}/api/scheduled-task/status', timeout=5)
        if r.status_code == 200:
            data = r.json()
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                status_text = '运行中' if data['is_running'] else '等待中'
                st.metric('当前状态', status_text)
            if data.get('last_run'):
                lr = data['last_run']
                with col_s2:
                    st.metric('上次运行状态', {
                        'success': '✅ 成功', 'failed': '❌ 失败', 'running': '🔄 运行中'
                    }.get(lr.get('status', ''), '未知'))
                with col_s3:
                    st.metric('生成文案', f"{lr.get('contents_generated', 0)} 组")
    except Exception:
        st.info('无法获取任务状态，请确认后端已启动')

    # 运行历史列表
    st.markdown('---')
    st.markdown('### 运行历史')
    try:
        r = requests.get(f'{api_url}/api/scheduled-task/history', params={'limit': 20}, timeout=5)
        if r.status_code == 200:
            records = r.json()
            if not records:
                st.info('暂无运行记录，等待首次自动执行或点击手动触发')
            else:
                for rec in records:
                    started = rec['started_at'][:19].replace('T', ' ') if rec.get('started_at') else '未知'
                    finished = rec['finished_at'][:19].replace('T', ' ') if rec.get('finished_at') else '进行中'
                    status_icon = {
                        'success': '✅', 'failed': '❌', 'running': '🔄'
                    }.get(rec['status'], '❓')
                    summary = f"{status_icon} {started} — 抓取 {rec.get('topics_fetched',0)} 条话题 | 生成 {rec.get('contents_generated',0)} 组文案"

                    with st.expander(summary):
                        col_d1, col_d2 = st.columns(2)
                        with col_d1:
                            st.markdown(f'**开始时间**: {started}')
                            st.markdown(f'**结束时间**: {finished}')
                            st.markdown(f'**状态**: {rec["status"]}')
                        with col_d2:
                            st.markdown(f'**抓取话题**: {rec.get("topics_fetched", 0)} 条')
                            st.markdown(f'**生成文案**: {rec.get("contents_generated", 0)} 组')

                        # 预测结果
                        pred = rec.get('prediction')
                        if pred:
                            st.markdown('---')
                            st.markdown('**🔮 下一个热点预测**')
                            pc1, pc2, pc3 = st.columns(3)
                            with pc1:
                                st.markdown(f'**话题**: {pred.get("topic", "未知")}')
                            with pc2:
                                st.markdown(f'**置信度**: {pred.get("confidence", 0)}/100')
                            with pc3:
                                st.markdown(f'**最热平台**: {pred.get("hot_platform", "未知")}')

                            if pred.get('hot_tags'):
                                st.markdown(f'**热门标签**: {", ".join(pred["hot_tags"])}')
                            if pred.get('rising_topics'):
                                st.markdown(f'**上升话题**: {" | ".join(pred["rising_topics"])}')
                            if pred.get('reasons'):
                                for reason in pred['reasons']:
                                    st.markdown(f'- {reason}')

                            # 展示本次生成的文案
                            contents = pred.get('generated_contents', [])
                            if contents:
                                st.markdown('---')
                                st.markdown('**📝 本次生成文案**')
                                for i, item in enumerate(contents):
                                    title = item.get("title", "未知")
                                    platforms = item.get("platforms", [])
                                    previews = item.get("previews", {})
                                    image_url = item.get("image_url")
                                    with st.expander(f"📄 {title[:40]}"):
                                        st.caption(f"平台: {', '.join(platforms)}")
                                        for j, p in enumerate(platforms):
                                            preview = previews.get(p, "")
                                            if preview:
                                                st.markdown(f"**{p}**")
                                                st.text_area(
                                                    label=p,
                                                    value=preview,
                                                    height=200,
                                                    disabled=True,
                                                    label_visibility="collapsed",
                                                    key=f"task_{i}_{j}"
                                                )
                                        if image_url:
                                            st.markdown("---")
                                            st.markdown("**🖼️ 配图**")
                                            st.image(image_url, width=400)

                        # 错误信息
                        if rec.get('error_message'):
                            st.markdown('---')
                            st.error(f"错误: {rec['error_message']}")
        else:
            st.error('获取历史记录失败')
    except Exception as e:
        st.error(f'请求失败: {str(e)}')
