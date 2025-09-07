import streamlit as st
import os
import tempfile
import json
import datetime
import hashlib
from PIL import Image
import io
import warnings
from image_generator import ImageGenerator

# 忽略所有警告
warnings.filterwarnings("ignore")

# 体验码验证函数
def load_experience_codes():
    """从st.secrets加载体验码配置"""
    try:
        # 从st.secrets中读取体验码配置
        experience_codes = st.secrets.get('experience_codes', {})
        
        # 调试信息
        if not experience_codes:
            st.warning("⚠️ 未找到体验码配置，请检查 .streamlit/secrets.toml 文件")
            return None
        
        # 确保返回正确的格式
        return {'experience_codes': experience_codes}
    except Exception as e:
        st.error(f"体验码配置加载失败: {str(e)}")
        st.error("请检查 .streamlit/secrets.toml 文件格式是否正确")
        
        # 显示调试信息
        with st.expander("🔍 调试信息"):
            st.write("错误详情:", str(e))
            st.write("当前配置格式:")
            st.code("""
experience_codes = {"验证码1" = { "name" = "体验码001", "max_images" = 10, "description" = "描述1" },
"验证码2" = { "name" = "体验码002", "max_images" = 10, "description" = "描述2" }}
            """)
            st.write("或者使用表格格式:")
            st.code("""
[experience_codes]
验证码1 = { name = "体验码001", max_images = 10, description = "描述1" }
验证码2 = { name = "体验码002", max_images = 10, description = "描述2" }
            """)
        
        return None

def validate_experience_code(code):
    """验证体验码"""
    config = load_experience_codes()
    if not config:
        return False, None
    
    # 确保体验码是小写
    code = code.lower()
    
    # 检查体验码是否存在
    if code in config['experience_codes']:
        return True, config['experience_codes'][code]
    
    # 调试信息：显示可用的体验码（仅用于调试）
    with st.expander("🔍 可用体验码调试信息"):
        st.write("当前配置的体验码:")
        for key, value in config['experience_codes'].items():
            st.write(f"- {key}: {value.get('name', '未知')}")
        st.write(f"输入的体验码: '{code}'")
    
    return False, None


def get_code_hash(code):
    """生成验证码的哈希值用于跟踪"""
    return hashlib.sha256(code.encode('utf-8')).hexdigest()[:16]  # 使用前16位作为标识

def load_usage_stats():
    """加载使用统计（基于哈希）"""
    try:
        with open('usage_stats.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # 如果文件不存在，创建默认统计
        default_stats = {"usage_stats": {}}
        with open('usage_stats.json', 'w', encoding='utf-8') as f:
            json.dump(default_stats, f, ensure_ascii=False, indent=4)
        return default_stats

def save_usage_stats(stats):
    """保存使用统计（基于哈希）"""
    with open('usage_stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=4)

def get_remaining_images():
    """获取剩余可生成图片数量（基于哈希统计）"""
    if 'current_code' not in st.session_state or not st.session_state.current_code:
        return 0
    
    config = load_experience_codes()
    
    if not config or st.session_state.current_code not in config['experience_codes']:
        return 0
    
    max_images = config['experience_codes'][st.session_state.current_code]['max_images']
    
    # 使用哈希值跟踪使用次数
    code_hash = get_code_hash(st.session_state.current_code)
    usage_stats = load_usage_stats()
    
    # 从哈希统计中获取已生成数量
    if code_hash in usage_stats['usage_stats']:
        used_count = usage_stats['usage_stats'][code_hash]['total_generated']
    else:
        used_count = 0
    
    return max(0, max_images - used_count)

def increment_generated_count():
    """增加生成计数（基于哈希统计）"""
    if 'current_code' not in st.session_state or not st.session_state.current_code:
        return
    
    # 使用哈希值跟踪使用次数
    code_hash = get_code_hash(st.session_state.current_code)
    usage_stats = load_usage_stats()
    
    # 初始化统计（如果不存在）
    if code_hash not in usage_stats['usage_stats']:
        usage_stats['usage_stats'][code_hash] = {
            "total_generated": 0,
            "last_used": None,
            "first_used": None
        }
    
    # 更新统计
    usage_stats['usage_stats'][code_hash]['total_generated'] += 1
    usage_stats['usage_stats'][code_hash]['last_used'] = datetime.datetime.now().isoformat()
    
    # 如果是第一次使用，记录首次使用时间
    if usage_stats['usage_stats'][code_hash]['first_used'] is None:
        usage_stats['usage_stats'][code_hash]['first_used'] = datetime.datetime.now().isoformat()
    
    # 保存统计
    save_usage_stats(usage_stats)
    
    # 同时更新session state用于显示
    if 'generated_count' not in st.session_state:
        st.session_state.generated_count = 0
    st.session_state.generated_count = usage_stats['usage_stats'][code_hash]['total_generated']

# 图片方向处理函数
def fix_image_orientation(image):
    """修复图片方向问题"""
    try:
        # 检查图片是否有EXIF信息
        if hasattr(image, '_getexif') and image._getexif():
            exif = image._getexif()
            if exif:
                # 获取方向信息
                orientation = exif.get(274)  # 274是方向标签的ID
                if orientation:
                    # 根据方向信息旋转图片
                    if orientation == 3:
                        image = image.rotate(180, expand=True)
                    elif orientation == 6:
                        image = image.rotate(270, expand=True)
                    elif orientation == 8:
                        image = image.rotate(90, expand=True)
    except Exception as e:
        # 如果处理失败，返回原图
        pass
    return image

# 页面配置
st.set_page_config(
    page_title="AI 虚拟换装系统",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #1f77b4;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #666;
        text-align: center;
        margin-bottom: 3rem;
    }
    .upload-section {
        background-color: #f8f9fa;
        padding: 2rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .result-section {
        background-color: #e8f5e8;
        padding: 2rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .stButton>button {
        width: 100%;
        height: 3rem;
        font-size: 1.2rem;
        background-color: #1f77b4;
        color: white;
        border: none;
        border-radius: 5px;
    }
    .stButton>button:hover {
        background-color: #1565c0;
    }
</style>
""", unsafe_allow_html=True)

# 体验码验证区域
st.markdown('<div class="upload-section">', unsafe_allow_html=True)
st.markdown('<h2 style="text-align: center; color: #1f77b4;">🔐 体验码验证</h2>', unsafe_allow_html=True)

# 检查是否已经验证过体验码
if 'current_code' not in st.session_state or not st.session_state.current_code:
    # 显示体验码输入界面
    st.markdown("""
    <div style="text-align: center; margin: 2rem 0;">
        <p style="font-size: 1.2rem; color: #666;">请输入体验码以开始使用AI虚拟换装系统</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        experience_code = st.text_input(
            "体验码",
            placeholder="请输入您的体验码",
            help="请输入有效的体验码以解锁功能",
            key="experience_code_input"
        )
        
        if st.button("🔓 验证体验码", use_container_width=True, key="verify_code"):
            if experience_code:
                # 体验码现在是小写字母+数字，不需要转换为大写
                is_valid, code_info = validate_experience_code(experience_code.lower())
                if is_valid:
                    st.session_state.current_code = experience_code.lower()
                    
                    # 从哈希统计中获取已生成数量
                    code_hash = get_code_hash(experience_code.lower())
                    usage_stats = load_usage_stats()
                    if code_hash in usage_stats['usage_stats']:
                        st.session_state.generated_count = usage_stats['usage_stats'][code_hash]['total_generated']
                    else:
                        st.session_state.generated_count = 0
                    
                    st.success(f"✅ 体验码验证成功！欢迎使用 {code_info['name']}")
                    st.rerun()
                else:
                    st.error("❌ 体验码无效，请检查后重试")
            else:
                st.error("❌ 请输入体验码")
    
    # 显示体验码说明
    with st.expander("💡 体验码说明"):
        st.markdown("""
        **体验码功能说明：**
        - 每个体验码支持生成 **10张图片**
        - 体验码验证后即可使用所有换装功能
        - 生成次数用完后需要更换新的体验码
        """)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()  # 停止执行后续代码，直到体验码验证通过

else:
    # 显示当前体验码状态
    config = load_experience_codes()
    if config and st.session_state.current_code in config['experience_codes']:
        code_info = config['experience_codes'][st.session_state.current_code]
        remaining = get_remaining_images()
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.success(f"✅ 当前体验码：{code_info['name']}")
            st.info(f"📊 剩余可生成图片：{remaining} 张")
            
            if remaining <= 0:
                st.error("⚠️ 体验码生成次数已用完，请更换新的体验码")
                if st.button("🔄 更换体验码", use_container_width=True, key="change_code"):
                    st.session_state.current_code = None
                    st.session_state.generated_count = 0
                    st.rerun()
            else:
                if st.button("🔄 更换体验码", use_container_width=True, key="change_code"):
                    st.session_state.current_code = None
                    st.session_state.generated_count = 0
                    st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# 主标题
st.markdown('<h1 class="main-header">👗 AI 虚拟换装系统</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">上传你的人像照片和服装图片，AI将为你生成完美的换装效果</p>', unsafe_allow_html=True)

# 侧边栏配置
with st.sidebar:
    st.markdown("---")
    st.header("📋 使用说明")
    st.markdown("""
    1. **上传人像照片** - 选择单张或多张清晰的人像照片
    2. **上传服装图片** - 选择单张或多张要试穿的服装或饰品图片
    3. **选择功能** - 系统会根据人像和服装数量自动显示相应功能
    4. **点击生成** - AI将为你合成换装效果
    5. **查看结果** - 下载生成的换装图片
    """)
    
    st.markdown("---")
    st.header("💡 小贴士")
    st.markdown("""
    - **体验码限制**：每个体验码支持生成10张图片
    - 人像照片越清晰，效果越好
    - 服装或饰品图片最好是正面展示
    - 生成过程需要几秒钟，请耐心等待
    - 支持多种换装功能
        - 👔 基础试衣：将单张服装图片与单张人像合成，生成最基础的换装效果。
        - 🎨 多图融合：将多张服装图片的元素融合到一张人像中，适合快速预览整体搭配效果。
        - 👕 分别试穿：每张服装图片分别与人像合成，适合详细对比每件服装的效果。
    """)

# 主界面 - 三列布局
col1, col2, col3 = st.columns([1, 1, 1])

# 左侧列 - 上传人像照片
with col1:
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    st.header("📸 上传人像照片")
    
    # 支持单张或多张人像上传
    person_files = st.file_uploader(
        "选择人像照片...", 
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        help="请上传清晰的人像照片，支持单张或多张，支持JPG、PNG格式"
    )
    
    if person_files:
        if len(person_files) == 1:
            st.success("🎉 已上传 1 张人像照片")
        else:
            st.success(f"🎉 已上传 {len(person_files)} 张人像照片")
        
        # 显示上传的人像
        for i, person_file in enumerate(person_files):
            person_image = Image.open(person_file)
            # 修复图片方向
            person_image = fix_image_orientation(person_image)
            st.image(person_image, caption=f"人像照片 {i+1}", use_column_width=True)
            
            # 显示文件信息
            file_size = len(person_file.getvalue()) / 1024  # KB
            st.info(f"人像照片 {i+1} 大小: {file_size:.1f} KB")
            
            # 添加分隔线（除了最后一张图片）
            if i < len(person_files) - 1:
                st.markdown("---")
    st.markdown('</div>', unsafe_allow_html=True)

# 中间列 - 上传服装图片
with col2:
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    st.header("👕 上传服装图片")
    clothes_files = st.file_uploader(
        "选择服装图片...", 
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        help="请上传要试穿的服装图片，支持多张图片，支持JPG、PNG格式"
    )
    
    if clothes_files:
        # 显示上传的服装图片
        for i, clothes_file in enumerate(clothes_files):
            clothes_image = Image.open(clothes_file)
            # 修复图片方向
            clothes_image = fix_image_orientation(clothes_image)
            st.image(clothes_image, caption=f"服装图片 {i+1}", use_column_width=True)
            
            # 显示文件信息
            file_size = len(clothes_file.getvalue()) / 1024  # KB
            st.info(f"服装图片 {i+1} 大小: {file_size:.1f} KB")
            
            # 添加分隔线（除了最后一张图片）
            if i < len(clothes_files) - 1:
                st.markdown("---")
    st.markdown('</div>', unsafe_allow_html=True)

# 右侧列 - 生成换装效果
with col3:
    st.markdown('<div class="result-section">', unsafe_allow_html=True)
    st.header("🎨 换装效果")
    
    # 检查是否有上传的文件
    has_person = person_files
    has_clothes = clothes_files
    
    if has_person and has_clothes:
        # 根据人像和服装数量创建不同的选项卡
        if len(person_files) == 1 and len(clothes_files) == 1:
            # 基础试衣：1张人像 + 1张服装
            tab1, tab2, tab3 = st.tabs(["👔 基础试衣", "🎨 多图融合", "👕 分别试穿"])
        elif len(person_files) == 1 and len(clothes_files) > 1:
            # 单人多衣：1张人像 + 多张服装
            tab1, tab2 = st.tabs(["🎨 多图融合", "👕 分别试穿"])
        elif len(person_files) > 1:
            # 多人场景：多张人像
            tab1, tab2, tab3 = st.tabs(["🎨 多图融合", "👕 分别试穿", "🎭 多场景换装"])
        
        # 基础试衣功能（仅在1张人像+1张服装时显示）
        if len(person_files) == 1 and len(clothes_files) == 1:
            with tab1:
                st.markdown("**👔 基础试衣**：将单张服装图片与单张人像合成，生成最基础的换装效果。")
                
                # 如果之前已经生成了基础试衣图片，显示历史记录
                if hasattr(st.session_state, 'basic_results') and st.session_state.basic_results:
                    st.success(f"🎉 已生成 {len(st.session_state.basic_results)} 张基础试衣效果图片")
                    
                    # 显示所有基础试衣历史图片
                    for i, (image_data, timestamp) in enumerate(st.session_state.basic_results):
                        st.markdown(f"### 👔 基础试衣效果 {i+1} (生成时间: {timestamp})")
                        
                        # 从session state恢复图片
                        import io
                        result_image = Image.open(io.BytesIO(image_data))
                        st.image(result_image, caption=f"AI生成的基础试衣效果 {i+1}", use_column_width=True)
                        
                        # 下载按钮
                        st.download_button(
                            label=f"📥 下载基础试衣图片 {i+1}",
                            data=image_data,
                            file_name=f"basic_result_{i+1}.png",
                            mime="image/png",
                            use_container_width=True,
                            key=f"download_basic_{i}"
                        )
                        
                        # 显示文件信息
                        file_size = len(image_data) / 1024  # KB
                        st.info(f"基础试衣图片 {i+1} 大小: {file_size:.1f} KB")
                        
                        # 添加清除按钮
                        if st.button(f"🗑️ 清除基础试衣图片 {i+1}", use_container_width=True, key=f"clear_basic_{i}"):
                            st.session_state.basic_results.pop(i)
                            st.rerun()
                        
                        # 添加分隔线（除了最后一张图片）
                        if i < len(st.session_state.basic_results) - 1:
                            st.markdown("---")
                    
                    # 添加清除所有基础试衣结果的按钮
                    if st.button("🗑️ 清除所有基础试衣结果", use_container_width=True, key="clear_all_basic"):
                        st.session_state.basic_results = []
                        st.rerun()
                
                # 检查剩余生成次数
                remaining = get_remaining_images()
                if remaining <= 0:
                    st.error("⚠️ 体验码生成次数已用完，请更换新的体验码")
                    st.stop()
                
                # 基础试衣按钮
                basic_button = st.button("👔 开始基础试衣", use_container_width=True)
                
                if basic_button:
                    try:
                        # 显示进度
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # 创建临时文件
                        with tempfile.TemporaryDirectory() as temp_dir:
                            # 保存人像文件
                            person_path = os.path.join(temp_dir, "person.jpg")
                            output_path = os.path.join(temp_dir, "basic_try_on_result")
                            
                            # 保存人像文件
                            status_text.text("正在处理人像文件...")
                            progress_bar.progress(0.3)  # 30%
                            # 读取并修复图片方向
                            person_image = Image.open(person_files[0])
                            person_image = fix_image_orientation(person_image)
                            
                            # 转换为RGB模式（如果图片是RGBA模式）
                            if person_image.mode == 'RGBA':
                                # 创建白色背景
                                background = Image.new('RGB', person_image.size, (255, 255, 255))
                                # 将RGBA图片粘贴到白色背景上
                                background.paste(person_image, mask=person_image.split()[-1])  # 使用alpha通道作为mask
                                person_image = background
                            elif person_image.mode != 'RGB':
                                person_image = person_image.convert('RGB')
                            
                            # 保存修复后的图片
                            person_image.save(person_path, "JPEG", quality=95)
                            
                            # 保存服装文件
                            status_text.text("正在处理服装文件...")
                            progress_bar.progress(0.6)  # 60%
                            # 读取并修复图片方向
                            clothes_image = Image.open(clothes_files[0])
                            clothes_image = fix_image_orientation(clothes_image)
                            
                            # 转换为RGB模式（如果图片是RGBA模式）
                            if clothes_image.mode == 'RGBA':
                                # 创建白色背景
                                background = Image.new('RGB', clothes_image.size, (255, 255, 255))
                                # 将RGBA图片粘贴到白色背景上
                                background.paste(clothes_image, mask=clothes_image.split()[-1])  # 使用alpha通道作为mask
                                clothes_image = background
                            elif clothes_image.mode != 'RGB':
                                clothes_image = clothes_image.convert('RGB')
                            
                            # 保存修复后的图片
                            clothes_path = os.path.join(temp_dir, "clothes.jpg")
                            clothes_image.save(clothes_path, "JPEG", quality=95)
                            
                            # 调用图像生成器
                            status_text.text("正在调用AI生成基础试衣效果...")
                            progress_bar.progress(0.8)  # 80%
                            
                            try:
                                # 在API调用前检查剩余次数
                                remaining_before = get_remaining_images()
                                if remaining_before <= 0:
                                    st.error("⚠️ 体验码生成次数已用完，无法继续生成")
                                    success = False
                                else:
                                    # 初始化ImageGenerator
                                    generator = ImageGenerator()
                                    
                                    # 构建图片路径列表（人像 + 服装）
                                    image_paths = [person_path, clothes_path]
                                    
                                    # 添加重试机制
                                    max_retries = 3
                                    retry_count = 0
                                    success = False
                                    
                                    while retry_count < max_retries and not success:
                                        try:
                                            status_text.text(f"正在调用AI生成基础试衣效果... (尝试 {retry_count + 1}/{max_retries})")
                                            success = generator.generate(
                                                image_paths=image_paths,
                                                output_path=output_path
                                            )
                                            if success:
                                                break
                                        except Exception as retry_error:
                                            retry_count += 1
                                            if retry_count < max_retries:
                                                st.warning(f"⚠️ 第{retry_count}次尝试失败，正在重试...")
                                                import time
                                                time.sleep(2)  # 等待2秒后重试
                                            else:
                                                # 最后一次尝试失败，抛出异常
                                                raise retry_error
                                
                            except Exception as api_error:
                                st.error(f"❌ API调用失败: {str(api_error)}")
                                success = False
                            
                            progress_bar.progress(0.9)  # 90%
                            
                            if success:
                                # 查找生成的文件
                                generated_files = []
                                for file in os.listdir(temp_dir):
                                    if file.startswith("basic_try_on_result") and file.endswith(('.png', '.jpg', '.jpeg')):
                                        generated_files.append(os.path.join(temp_dir, file))
                                
                                if generated_files:
                                    # 显示结果
                                    progress_bar.progress(1.0)  # 100%
                                    status_text.text("生成完成！")
                                    
                                    st.success("🎉 基础试衣效果生成成功！")
                                    
                                    # 将生成的图片数据保存到session state
                                    result_image_path = generated_files[0]  # 获取生成的文件路径
                                    with open(result_image_path, "rb") as file:
                                        file_data = file.read()
                                    
                                    # 保存图片数据到session state
                                    import datetime
                                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    
                                    # 初始化图片列表（如果不存在）
                                    if 'basic_results' not in st.session_state:
                                        st.session_state.basic_results = []
                                    
                                    # 添加新图片到列表
                                    st.session_state.basic_results.append((file_data, timestamp))
                                    
                                    # 增加生成计数
                                    increment_generated_count()
                                    
                                    # 显示生成的图片
                                    result_image = Image.open(result_image_path)
                                    st.image(result_image, caption="AI生成的基础试衣效果", use_column_width=True)
                                    
                                    # 自动刷新页面以更新剩余次数显示
                                    st.rerun()
                                    
                                    # 下载按钮
                                    st.download_button(
                                        label="📥 下载基础试衣图片",
                                        data=file_data,
                                        file_name="basic_result.png",
                                        mime="image/png",
                                        use_container_width=True,
                                        key="download_new_basic"
                                    )
                                    
                                    # 显示文件信息
                                    file_size = len(file_data) / 1024  # KB
                                    st.info(f"基础试衣图片大小: {file_size:.1f} KB")
                                    
                                else:
                                    st.error("❌ 生成失败：未找到输出文件")
                            else:
                                st.error("❌ 生成失败：请检查输入文件或API连接")
                        
                    except Exception as e:
                        st.error(f"❌ 处理过程中出现错误: {str(e)}")
                        st.exception(e)
        
        # 多图融合功能
        with tab2 if len(person_files) == 1 and len(clothes_files) == 1 else tab1:
            if len(person_files) == 1:
                st.markdown("**🎨 多图融合**：将多张服装图片的元素融合到一张人像中，适合快速预览整体搭配效果。")
            else:
                st.markdown("**🎨 多图融合**：将多张服装图片的元素融合到第一张人像中，适合快速预览整体搭配效果。")
            
            # 如果之前已经生成了融合图片，显示历史记录
            if hasattr(st.session_state, 'fusion_results') and st.session_state.fusion_results:
                st.success(f"🎉 已生成 {len(st.session_state.fusion_results)} 张融合效果图片")
                
                # 显示所有融合历史图片
                for i, (image_data, timestamp) in enumerate(st.session_state.fusion_results):
                    st.markdown(f"### 🎨 融合效果 {i+1} (生成时间: {timestamp})")
                    
                    # 从session state恢复图片
                    import io
                    result_image = Image.open(io.BytesIO(image_data))
                    st.image(result_image, caption=f"AI生成的融合效果 {i+1}", use_column_width=True)
                    
                    # 下载按钮
                    st.download_button(
                        label=f"📥 下载融合图片 {i+1}",
                        data=image_data,
                        file_name=f"fusion_result_{i+1}.png",
                        mime="image/png",
                        use_container_width=True,
                        key=f"download_fusion_{i}"
                    )
                    
                    # 显示文件信息
                    file_size = len(image_data) / 1024  # KB
                    st.info(f"融合图片 {i+1} 大小: {file_size:.1f} KB")
                    
                    # 添加清除按钮
                    if st.button(f"🗑️ 清除融合图片 {i+1}", use_container_width=True, key=f"clear_fusion_{i}"):
                        st.session_state.fusion_results.pop(i)
                        st.rerun()
                    
                    # 添加分隔线（除了最后一张图片）
                    if i < len(st.session_state.fusion_results) - 1:
                        st.markdown("---")
                
                # 添加清除所有融合结果的按钮
                if st.button("🗑️ 清除所有融合结果", use_container_width=True, key="clear_all_fusion"):
                    st.session_state.fusion_results = []
                    st.rerun()
            
            # 检查剩余生成次数
            remaining = get_remaining_images()
            if remaining <= 0:
                st.error("⚠️ 体验码生成次数已用完，请更换新的体验码")
                st.stop()
            
            # 多图融合按钮
            fusion_button = st.button("🚀 融合所有服装", use_container_width=True)
            
            if fusion_button:
                try:
                    # 显示进度
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # 创建临时文件
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # 根据人像数量处理人像文件
                        if len(person_files) == 1:
                            person_path = os.path.join(temp_dir, "person.jpg")
                            output_path = os.path.join(temp_dir, "virtual_try_on_result")
                            
                            # 保存人像文件
                            status_text.text("正在处理人像文件...")
                            progress_bar.progress(0.2)  # 20%
                            # 读取并修复图片方向
                            person_image = Image.open(person_files[0])
                            person_image = fix_image_orientation(person_image)
                            
                            # 转换为RGB模式（如果图片是RGBA模式）
                            if person_image.mode == 'RGBA':
                                # 创建白色背景
                                background = Image.new('RGB', person_image.size, (255, 255, 255))
                                # 将RGBA图片粘贴到白色背景上
                                background.paste(person_image, mask=person_image.split()[-1])  # 使用alpha通道作为mask
                                person_image = background
                            elif person_image.mode != 'RGB':
                                person_image = person_image.convert('RGB')
                            
                            # 保存修复后的图片
                            person_image.save(person_path, "JPEG", quality=95)
                        else:  # 多张人像模式
                            # 使用第一张人像进行融合
                            person_path = os.path.join(temp_dir, "person.jpg")
                            output_path = os.path.join(temp_dir, "virtual_try_on_result")
                            
                            # 保存第一张人像文件
                            status_text.text("正在处理第一张人像文件...")
                            progress_bar.progress(0.2)  # 20%
                            # 读取并修复图片方向
                            person_image = Image.open(person_files[0])
                            person_image = fix_image_orientation(person_image)
                            
                            # 转换为RGB模式（如果图片是RGBA模式）
                            if person_image.mode == 'RGBA':
                                # 创建白色背景
                                background = Image.new('RGB', person_image.size, (255, 255, 255))
                                # 将RGBA图片粘贴到白色背景上
                                background.paste(person_image, mask=person_image.split()[-1])  # 使用alpha通道作为mask
                                person_image = background
                            elif person_image.mode != 'RGB':
                                person_image = person_image.convert('RGB')
                            
                            # 保存修复后的图片
                            person_image.save(person_path, "JPEG", quality=95)
                        
                        # 保存所有服装文件
                        clothes_paths = []
                        total_clothes = len(clothes_files)
                        for i, clothes_file in enumerate(clothes_files):
                            status_text.text(f"正在处理服装文件 {i+1}/{total_clothes}...")
                            progress_per_clothes = 0.2 / total_clothes  # 20% 分配给服装处理
                            progress_bar.progress(0.2 + (i + 1) * progress_per_clothes)
                            
                            # 读取并修复图片方向
                            clothes_image = Image.open(clothes_file)
                            clothes_image = fix_image_orientation(clothes_image)
                            
                            # 转换为RGB模式（如果图片是RGBA模式）
                            if clothes_image.mode == 'RGBA':
                                # 创建白色背景
                                background = Image.new('RGB', clothes_image.size, (255, 255, 255))
                                # 将RGBA图片粘贴到白色背景上
                                background.paste(clothes_image, mask=clothes_image.split()[-1])  # 使用alpha通道作为mask
                                clothes_image = background
                            elif clothes_image.mode != 'RGB':
                                clothes_image = clothes_image.convert('RGB')
                            
                            # 保存修复后的图片
                            clothes_path = os.path.join(temp_dir, f"clothes_{i+1}.jpg")
                            clothes_image.save(clothes_path, "JPEG", quality=95)
                            clothes_paths.append(clothes_path)
                        
                        # 调用图像生成器
                        status_text.text("正在调用AI生成融合效果...")
                        progress_bar.progress(0.6)  # 60%
                        
                        try:
                            # 在API调用前检查剩余次数
                            remaining_before = get_remaining_images()
                            if remaining_before <= 0:
                                st.error("⚠️ 体验码生成次数已用完，无法继续生成")
                                success = False
                            else:
                                # 初始化ImageGenerator
                                generator = ImageGenerator()
                                
                                # 构建所有图片路径列表（人像 + 所有服装）
                                all_image_paths = [person_path] + clothes_paths
                                
                                # 添加重试机制
                                max_retries = 3
                                retry_count = 0
                                success = False
                                
                                while retry_count < max_retries and not success:
                                    try:
                                        status_text.text(f"正在调用AI生成融合效果... (尝试 {retry_count + 1}/{max_retries})")
                                        success = generator.generate(
                                            image_paths=all_image_paths,
                                            output_path=output_path
                                        )
                                        if success:
                                            break
                                    except Exception as retry_error:
                                        retry_count += 1
                                        if retry_count < max_retries:
                                            st.warning(f"⚠️ 第{retry_count}次尝试失败，正在重试...")
                                            import time
                                            time.sleep(2)  # 等待2秒后重试
                                        else:
                                            # 最后一次尝试失败，抛出异常
                                            raise retry_error
                            
                        except Exception as api_error:
                            st.error(f"❌ API调用失败: {str(api_error)}")
                            st.error("可能的原因：")
                            st.error("1. API密钥无效或已过期")
                            st.error("2. 网络连接问题（SSL连接中断）")
                            st.error("3. API配额已用完")
                            st.error("4. 请求被Google服务器拒绝")
                            st.error("5. 防火墙或代理设置问题")
                            
                            # 显示调试信息
                            with st.expander("调试信息"):
                                st.write(f"错误类型: {type(api_error).__name__}")
                                st.write(f"错误详情: {str(api_error)}")
                                
                                # 提供解决方案
                                st.write("**解决方案：**")
                                st.write("1. 检查网络连接是否稳定")
                                st.write("2. 尝试使用VPN或更换网络")
                                st.write("3. 检查防火墙设置")
                                st.write("4. 验证API密钥是否正确")
                            
                            success = False
                        
                        progress_bar.progress(0.8)  # 80%
                        
                        if success:
                            # 查找生成的文件
                            generated_files = []
                            for file in os.listdir(temp_dir):
                                if file.startswith("virtual_try_on_result") and file.endswith(('.png', '.jpg', '.jpeg')):
                                    generated_files.append(os.path.join(temp_dir, file))
                            
                            if generated_files:
                                # 显示结果
                                progress_bar.progress(1.0)  # 100%
                                status_text.text("生成完成！")
                                
                                st.success("🎉 融合效果生成成功！")
                                
                                # 将生成的图片数据保存到session state
                                result_image_path = generated_files[0]  # 获取生成的文件路径
                                with open(result_image_path, "rb") as file:
                                    file_data = file.read()
                                
                                # 保存图片数据到session state（使用列表存储多张图片）
                                import datetime
                                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                
                                # 初始化图片列表（如果不存在）
                                if 'fusion_results' not in st.session_state:
                                    st.session_state.fusion_results = []
                                
                                # 添加新图片到列表
                                st.session_state.fusion_results.append((file_data, timestamp))
                                
                                # 增加生成计数
                                increment_generated_count()
                                
                                # 显示生成的图片
                                result_image = Image.open('./' + result_image_path)
                                st.image(result_image, caption="AI生成的融合效果", use_column_width=True)
                                
                                # 自动刷新页面以更新剩余次数显示
                                st.rerun()
                                
                                # 下载按钮
                                st.download_button(
                                    label="📥 下载融合图片",
                                    data=file_data,
                                    file_name="fusion_result.png",
                                    mime="image/png",
                                    use_container_width=True,
                                    key="download_new_fusion"
                                )
                                
                                # 显示文件信息
                                file_size = len(file_data) / 1024  # KB
                                st.info(f"融合图片大小: {file_size:.1f} KB")
                                
                            else:
                                st.error("❌ 生成失败：未找到输出文件")
                        else:
                            st.error("❌ 生成失败：请检查输入文件或API连接")
                            
                except Exception as e:
                    st.error(f"❌ 处理过程中出现错误: {str(e)}")
                    st.exception(e)
        
        # 分别试穿功能
        with tab3 if len(person_files) == 1 and len(clothes_files) == 1 else tab2:
            if len(person_files) == 1:
                st.markdown("**👕 分别试穿**：每张服装图片分别与人像合成，适合详细对比每件服装的效果。")
            else:
                st.markdown("**👕 分别试穿**：每张服装图片分别与第一张人像合成，适合详细对比每件服装的效果。")
            
            # 如果之前已经生成了分别试穿图片，显示历史记录
            if hasattr(st.session_state, 'individual_results') and st.session_state.individual_results:
                st.success(f"🎉 已生成 {len(st.session_state.individual_results)} 张分别试穿效果图片")
                
                # 显示所有分别试穿历史图片
                for i, (image_data, timestamp, clothes_name) in enumerate(st.session_state.individual_results):
                    st.markdown(f"### 👕 试穿效果 {i+1} - {clothes_name} (生成时间: {timestamp})")
                    
                    # 从session state恢复图片
                    import io
                    result_image = Image.open(io.BytesIO(image_data))
                    st.image(result_image, caption=f"AI生成的试穿效果 {i+1}", use_column_width=True)
                    
                    # 下载按钮
                    st.download_button(
                        label=f"📥 下载试穿图片 {i+1}",
                        data=image_data,
                        file_name=f"individual_result_{i+1}.png",
                        mime="image/png",
                        use_container_width=True,
                        key=f"download_individual_{i}"
                    )
                    
                    # 显示文件信息
                    file_size = len(image_data) / 1024  # KB
                    st.info(f"试穿图片 {i+1} 大小: {file_size:.1f} KB")
                    
                    # 添加清除按钮
                    if st.button(f"🗑️ 清除试穿图片 {i+1}", use_container_width=True, key=f"clear_individual_{i}"):
                        st.session_state.individual_results.pop(i)
                        st.rerun()
                    
                    # 添加分隔线（除了最后一张图片）
                    if i < len(st.session_state.individual_results) - 1:
                        st.markdown("---")
                
                # 添加清除所有分别试穿结果的按钮
                if st.button("🗑️ 清除所有试穿结果", use_container_width=True, key="clear_all_individual"):
                    st.session_state.individual_results = []
                    st.rerun()
            
            # 检查剩余生成次数
            remaining = get_remaining_images()
            if remaining <= 0:
                st.error("⚠️ 体验码生成次数已用完，请更换新的体验码")
                st.stop()
            
            # 分别试穿按钮
            individual_button = st.button("👕 分别试穿", use_container_width=True)
            
            if individual_button:
                try:
                    # 显示进度
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # 创建临时文件
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # 保存人像文件
                        person_path = os.path.join(temp_dir, "person.jpg")
                        
                        # 保存人像文件
                        status_text.text("正在处理人像文件...")
                        progress_bar.progress(0.1)  # 10%
                        # 读取并修复图片方向
                        person_image = Image.open(person_files[0])
                        person_image = fix_image_orientation(person_image)
                        
                        # 转换为RGB模式（如果图片是RGBA模式）
                        if person_image.mode == 'RGBA':
                            # 创建白色背景
                            background = Image.new('RGB', person_image.size, (255, 255, 255))
                            # 将RGBA图片粘贴到白色背景上
                            background.paste(person_image, mask=person_image.split()[-1])  # 使用alpha通道作为mask
                            person_image = background
                        elif person_image.mode != 'RGB':
                            person_image = person_image.convert('RGB')
                        
                        # 保存修复后的图片
                        person_image.save(person_path, "JPEG", quality=95)
                        
                        # 初始化结果列表
                        if 'individual_results' not in st.session_state:
                            st.session_state.individual_results = []
                        
                        # 分别处理每张服装图片
                        total_clothes = len(clothes_files)
                        success_count = 0
                        
                        for i, clothes_file in enumerate(clothes_files):
                            try:
                                # 在每次循环开始时检查剩余次数
                                remaining_before = get_remaining_images()
                                if remaining_before <= 0:
                                    st.error(f"⚠️ 体验码生成次数已用完，无法生成服装 {i+1} 的试穿效果")
                                    st.warning(f"已成功生成 {success_count} 张图片，剩余 {len(clothes_files) - i} 张服装无法处理")
                                    break  # 跳出循环，不再处理剩余服装
                                
                                status_text.text(f"正在处理服装 {i+1}/{total_clothes}... (剩余次数: {remaining_before})")
                                progress_bar.progress(0.1 + (i + 1) * 0.8 / total_clothes)
                                
                                # 读取并修复图片方向
                                clothes_image = Image.open(clothes_file)
                                clothes_image = fix_image_orientation(clothes_image)
                                
                                # 转换为RGB模式（如果图片是RGBA模式）
                                if clothes_image.mode == 'RGBA':
                                    # 创建白色背景
                                    background = Image.new('RGB', clothes_image.size, (255, 255, 255))
                                    # 将RGBA图片粘贴到白色背景上
                                    background.paste(clothes_image, mask=clothes_image.split()[-1])  # 使用alpha通道作为mask
                                    clothes_image = background
                                elif clothes_image.mode != 'RGB':
                                    clothes_image = clothes_image.convert('RGB')
                                
                                # 保存修复后的图片
                                clothes_path = os.path.join(temp_dir, f"clothes_{i+1}.jpg")
                                clothes_image.save(clothes_path, "JPEG", quality=95)
                                
                                # 调用图像生成器
                                status_text.text(f"正在生成服装 {i+1} 的试穿效果...")
                                
                                # 初始化ImageGenerator
                                generator = ImageGenerator()
                                
                                # 构建图片路径列表（人像 + 单张服装）
                                single_image_paths = [person_path, clothes_path]
                                output_path = os.path.join(temp_dir, f"individual_result_{i+1}")
                                
                                # 添加重试机制
                                max_retries = 3
                                retry_count = 0
                                success = False
                                
                                while retry_count < max_retries and not success:
                                    try:
                                        status_text.text(f"正在生成服装 {i+1} 的试穿效果... (尝试 {retry_count + 1}/{max_retries})")
                                        success = generator.generate(
                                            image_paths=single_image_paths,
                                            output_path=output_path
                                        )
                                        if success:
                                            break
                                    except Exception as retry_error:
                                        retry_count += 1
                                        if retry_count < max_retries:
                                            st.warning(f"⚠️ 服装 {i+1} 第{retry_count}次尝试失败，正在重试...")
                                            import time
                                            time.sleep(2)  # 等待2秒后重试
                                        else:
                                            # 最后一次尝试失败，抛出异常
                                            raise retry_error
                                
                                if success:
                                    # 查找生成的文件
                                    generated_files = []
                                    for file in os.listdir(temp_dir):
                                        if file.startswith(f"individual_result_{i+1}") and file.endswith(('.png', '.jpg', '.jpeg')):
                                            generated_files.append(os.path.join(temp_dir, file))
                                    
                                    if generated_files:
                                        # 读取生成的图片
                                        result_image_path = generated_files[0]
                                        with open(result_image_path, "rb") as file:
                                            file_data = file.read()
                                        
                                        # 保存图片数据到session state
                                        import datetime
                                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        clothes_name = f"服装 {i+1}"
                                        
                                        # 添加新图片到列表
                                        st.session_state.individual_results.append((file_data, timestamp, clothes_name))
                                        success_count += 1
                                        
                                        # 增加生成计数
                                        increment_generated_count()
                                        
                                        # 注意：不在这里调用st.rerun()，避免中断循环
                                
                            except Exception as e:
                                st.error(f"❌ 处理服装 {i+1} 时出现错误: {str(e)}")
                                continue
                        
                        # 显示最终结果
                        progress_bar.progress(1.0)  # 100%
                        status_text.text("生成完成！")
                        
                        if success_count > 0:
                            st.success(f"🎉 分别试穿效果生成成功！共生成 {success_count} 张图片")
                            
                            # 在所有图片生成完成后刷新页面
                            st.rerun()
                            
                            # 显示所有生成的图片
                            for i, (image_data, timestamp, clothes_name) in enumerate(st.session_state.individual_results[-success_count:]):
                                st.markdown(f"### 👕 {clothes_name} 试穿效果")
                                
                                # 显示图片
                                result_image = Image.open(io.BytesIO(image_data))
                                st.image(result_image, caption=f"AI生成的{clothes_name}试穿效果", use_column_width=True)
                                
                                # 下载按钮
                                st.download_button(
                                    label=f"📥 下载{clothes_name}试穿图片",
                                    data=image_data,
                                    file_name=f"individual_result_{i+1}.png",
                                    mime="image/png",
                                    use_container_width=True,
                                    key=f"download_new_individual_{i}"
                                )
                                
                                # 显示文件信息
                                file_size = len(image_data) / 1024  # KB
                                st.info(f"{clothes_name}试穿图片大小: {file_size:.1f} KB")
                                
                                # 添加分隔线（除了最后一张图片）
                                if i < success_count - 1:
                                    st.markdown("---")
                        else:
                            st.error("❌ 分别试穿生成失败：没有成功生成任何图片")
                            
                except Exception as e:
                    st.error(f"❌ 处理过程中出现错误: {str(e)}")
                    st.exception(e)
        
        # 多场景换装功能（仅在多张人像模式下显示）
        if len(person_files) > 1:
            with tab3:
                st.markdown("**🎭 多场景换装**：为每张人像图片融合所有服装，生成多张换装效果图。")
                
                # 如果之前已经生成了多场景换装图片，显示历史记录
                if hasattr(st.session_state, 'multi_scene_results') and st.session_state.multi_scene_results:
                    st.success(f"🎉 已生成 {len(st.session_state.multi_scene_results)} 张多场景换装效果图片")
                    
                    # 显示所有多场景换装历史图片
                    for i, (image_data, timestamp, person_name) in enumerate(st.session_state.multi_scene_results):
                        st.markdown(f"### 🎭 {person_name} 换装效果 (生成时间: {timestamp})")
                        
                        # 从session state恢复图片
                        import io
                        result_image = Image.open(io.BytesIO(image_data))
                        st.image(result_image, caption=f"AI生成的{person_name}换装效果", use_column_width=True)
                        
                        # 下载按钮
                        st.download_button(
                            label=f"📥 下载{person_name}换装图片",
                            data=image_data,
                            file_name=f"multi_scene_result_{i+1}.png",
                            mime="image/png",
                            use_container_width=True,
                            key=f"download_multi_scene_{i}"
                        )
                        
                        # 显示文件信息
                        file_size = len(image_data) / 1024  # KB
                        st.info(f"{person_name}换装图片大小: {file_size:.1f} KB")
                        
                        # 添加清除按钮
                        if st.button(f"🗑️ 清除{person_name}换装图片", use_container_width=True, key=f"clear_multi_scene_{i}"):
                            st.session_state.multi_scene_results.pop(i)
                            st.rerun()
                        
                        # 添加分隔线（除了最后一张图片）
                        if i < len(st.session_state.multi_scene_results) - 1:
                            st.markdown("---")
                    
                    # 添加清除所有多场景换装结果的按钮
                    if st.button("🗑️ 清除所有多场景换装结果", use_container_width=True, key="clear_all_multi_scene"):
                        st.session_state.multi_scene_results = []
                        st.rerun()
                
                # 检查剩余生成次数
                remaining = get_remaining_images()
                if remaining <= 0:
                    st.error("⚠️ 体验码生成次数已用完，请更换新的体验码")
                    st.stop()
                
                # 多场景换装按钮
                multi_scene_button = st.button("🎭 多场景换装", use_container_width=True)
                
                if multi_scene_button:
                    try:
                        # 显示进度
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # 创建临时文件
                        with tempfile.TemporaryDirectory() as temp_dir:
                            # 初始化结果列表
                            if 'multi_scene_results' not in st.session_state:
                                st.session_state.multi_scene_results = []
                            
                            # 保存所有服装文件
                            clothes_paths = []
                            total_clothes = len(clothes_files)
                            for i, clothes_file in enumerate(clothes_files):
                                status_text.text(f"正在处理服装文件 {i+1}/{total_clothes}...")
                                progress_per_clothes = 0.1 / total_clothes  # 10% 分配给服装处理
                                progress_bar.progress((i + 1) * progress_per_clothes)
                                
                                # 读取并修复图片方向
                                clothes_image = Image.open(clothes_file)
                                clothes_image = fix_image_orientation(clothes_image)
                                
                                # 转换为RGB模式（如果图片是RGBA模式）
                                if clothes_image.mode == 'RGBA':
                                    # 创建白色背景
                                    background = Image.new('RGB', clothes_image.size, (255, 255, 255))
                                    # 将RGBA图片粘贴到白色背景上
                                    background.paste(clothes_image, mask=clothes_image.split()[-1])  # 使用alpha通道作为mask
                                    clothes_image = background
                                elif clothes_image.mode != 'RGB':
                                    clothes_image = clothes_image.convert('RGB')
                                
                                # 保存修复后的图片
                                clothes_path = os.path.join(temp_dir, f"clothes_{i+1}.jpg")
                                clothes_image.save(clothes_path, "JPEG", quality=95)
                                clothes_paths.append(clothes_path)
                            
                            # 处理每张人像图片
                            total_persons = len(person_files)
                            success_count = 0
                            
                            for i, person_file in enumerate(person_files):
                                try:
                                    # 在每次循环开始时检查剩余次数
                                    remaining_before = get_remaining_images()
                                    if remaining_before <= 0:
                                        st.error(f"⚠️ 体验码生成次数已用完，无法生成人像 {i+1} 的换装效果")
                                        st.warning(f"已成功生成 {success_count} 张图片，剩余 {len(person_files) - i} 张人像无法处理")
                                        break  # 跳出循环，不再处理剩余人像
                                    
                                    status_text.text(f"正在处理人像 {i+1}/{total_persons}... (剩余次数: {remaining_before})")
                                    progress_bar.progress(0.1 + (i + 1) * 0.8 / total_persons)
                                    
                                    # 读取并修复图片方向
                                    person_image = Image.open(person_file)
                                    person_image = fix_image_orientation(person_image)
                                    
                                    # 转换为RGB模式（如果图片是RGBA模式）
                                    if person_image.mode == 'RGBA':
                                        # 创建白色背景
                                        background = Image.new('RGB', person_image.size, (255, 255, 255))
                                        # 将RGBA图片粘贴到白色背景上
                                        background.paste(person_image, mask=person_image.split()[-1])  # 使用alpha通道作为mask
                                        person_image = background
                                    elif person_image.mode != 'RGB':
                                        person_image = person_image.convert('RGB')
                                    
                                    # 保存修复后的图片
                                    person_path = os.path.join(temp_dir, f"person_{i+1}.jpg")
                                    person_image.save(person_path, "JPEG", quality=95)
                                    
                                    # 调用图像生成器
                                    status_text.text(f"正在生成人像 {i+1} 的换装效果...")
                                    
                                    # 初始化ImageGenerator
                                    generator = ImageGenerator()
                                    
                                    # 构建图片路径列表（人像 + 所有服装）
                                    all_image_paths = [person_path] + clothes_paths
                                    output_path = os.path.join(temp_dir, f"multi_scene_result_{i+1}")
                                    
                                    # 添加重试机制
                                    max_retries = 3
                                    retry_count = 0
                                    success = False
                                    
                                    while retry_count < max_retries and not success:
                                        try:
                                            status_text.text(f"正在生成人像 {i+1} 的换装效果... (尝试 {retry_count + 1}/{max_retries})")
                                            success = generator.generate(
                                                image_paths=all_image_paths,
                                                output_path=output_path
                                            )
                                            if success:
                                                break
                                        except Exception as retry_error:
                                            retry_count += 1
                                            if retry_count < max_retries:
                                                st.warning(f"⚠️ 人像 {i+1} 第{retry_count}次尝试失败，正在重试...")
                                                import time
                                                time.sleep(2)  # 等待2秒后重试
                                            else:
                                                # 最后一次尝试失败，抛出异常
                                                raise retry_error
                                    
                                    if success:
                                        # 查找生成的文件
                                        generated_files = []
                                        for file in os.listdir(temp_dir):
                                            if file.startswith(f"multi_scene_result_{i+1}") and file.endswith(('.png', '.jpg', '.jpeg')):
                                                generated_files.append(os.path.join(temp_dir, file))
                                        
                                        if generated_files:
                                            # 读取生成的图片
                                            result_image_path = generated_files[0]
                                            with open(result_image_path, "rb") as file:
                                                file_data = file.read()
                                            
                                            # 保存图片数据到session state
                                            import datetime
                                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                            person_name = f"人像 {i+1}"
                                            
                                            # 添加新图片到列表
                                            st.session_state.multi_scene_results.append((file_data, timestamp, person_name))
                                            success_count += 1
                                            
                                            # 增加生成计数
                                            increment_generated_count()
                                            
                                            # 注意：不在这里调用st.rerun()，避免中断循环
                                
                                except Exception as e:
                                    st.error(f"❌ 处理人像 {i+1} 时出现错误: {str(e)}")
                                    continue
                            
                            # 显示最终结果
                            progress_bar.progress(1.0)  # 100%
                            status_text.text("生成完成！")
                            
                            if success_count > 0:
                                st.success(f"🎉 多场景换装效果生成成功！共生成 {success_count} 张图片")
                                
                                # 在所有图片生成完成后刷新页面
                                st.rerun()
                                
                                # 显示所有生成的图片
                                for i, (image_data, timestamp, person_name) in enumerate(st.session_state.multi_scene_results[-success_count:]):
                                    st.markdown(f"### 🎭 {person_name} 换装效果")
                                    
                                    # 显示图片
                                    result_image = Image.open(io.BytesIO(image_data))
                                    st.image(result_image, caption=f"AI生成的{person_name}换装效果", use_column_width=True)
                                    
                                    # 下载按钮
                                    st.download_button(
                                        label=f"📥 下载{person_name}换装图片",
                                        data=image_data,
                                        file_name=f"multi_scene_result_{i+1}.png",
                                        mime="image/png",
                                        use_container_width=True,
                                        key=f"download_new_multi_scene_{i}"
                                    )
                                    
                                    # 显示文件信息
                                    file_size = len(image_data) / 1024  # KB
                                    st.info(f"{person_name}换装图片大小: {file_size:.1f} KB")
                                    
                                    # 添加分隔线（除了最后一张图片）
                                    if i < success_count - 1:
                                        st.markdown("---")
                            else:
                                st.error("❌ 多场景换装生成失败：没有成功生成任何图片")
                                
                    except Exception as e:
                        st.error(f"❌ 处理过程中出现错误: {str(e)}")
                        st.exception(e)
    else:
        st.info("请先上传人像照片和服装图片")
    st.markdown('</div>', unsafe_allow_html=True)

# 页脚
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem;">
    <p>🤖 基于 Google Gemini AI 技术 | 📧 如有问题请联系技术支持</p>
    <p>© 2025 AI 虚拟换装系统</p>
</div>
""", unsafe_allow_html=True)