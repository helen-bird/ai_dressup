import base64
import mimetypes
import os
from google import genai
from google.genai import types
import streamlit as st


class ImageGenerator:
    """图像生成器类"""
    
    def __init__(self, config_path='config.json'):
        """
        初始化图像生成器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.api_key = None
        self.clothing_prompt = None
        self.client = None
        self._load_config()
        self._init_client()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            # 从 Streamlit secrets 中读取配置
            self.api_key = st.secrets['GEMINI_API_KEY']
            self.clothing_prompt = st.secrets['clothing_prompt']
            print("配置文件加载成功")
            print(f"提示文本: {self.clothing_prompt[:100]}...")
        except Exception as e:
            print(f"配置文件加载失败: {e}")
            raise
    
    def _init_client(self):
        """初始化API客户端"""
        try:
            self.client = genai.Client(api_key=self.api_key)
            print("API客户端初始化成功")
        except Exception as e:
            print(f"API客户端初始化失败: {e}")
            raise
    
    def _save_binary_file(self, file_name, data):
        """保存二进制文件"""
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(file_name)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                print(f"创建输出目录: {output_dir}")
            
            with open(file_name, "wb") as f:
                f.write(data)
            print(f"文件已保存: {file_name}")
        except Exception as e:
            print(f"文件保存失败: {e}")
            raise
    
    def _read_image_file(self, image_path):
        """读取本地图像文件并转换为Base64编码"""
        try:
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            print(f"读取图像文件失败: {e}")
            return None
    
    def _validate_image_file(self, file_path):
        """验证图像文件是否有效"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)
                if header.startswith(b'\x89PNG\r\n\x1a\n'):
                    return True, "PNG"
                elif header.startswith(b'\xff\xd8\xff'):
                    return True, "JPEG"
                else:
                    return False, f"未知格式: {header.hex()}"
        except Exception as e:
            return False, f"验证失败: {e}"
    
    def generate(self, image_paths, output_path, custom_prompt=None):
        """
        生成图像内容
        
        Args:
            image_paths: 图像路径列表，至少需要2个路径
            output_path: 输出图像路径
            custom_prompt: 自定义提示文本（可选）
        
        Returns:
            bool: 生成是否成功
        """
        # 验证输入参数
        if not isinstance(image_paths, (list, tuple)):
            print("错误：image_paths 必须是列表或元组")
            return False
        
        if len(image_paths) < 2:
            print("错误：至少需要2个图像路径")
            return False
        
        # 使用自定义提示文本或默认提示文本
        clothing_prompt = custom_prompt if custom_prompt else self.clothing_prompt
        
        print("正在读取图像文件...")
        print(f"共需要处理 {len(image_paths)} 个图像文件")
        
        # 读取所有图像文件
        image_data_list = []
        mime_type_list = []
        
        for i, image_path in enumerate(image_paths):
            print(f"正在读取第 {i+1} 个图像: {image_path}")
            image_data = self._read_image_file(image_path)
            if not image_data:
                print(f"图像文件读取失败: {image_path}")
                return False
            
            image_data_list.append(image_data)
            
            # 获取图像MIME类型
            mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
            mime_type_list.append(mime_type)
            print(f"图像 {i+1} MIME类型: {mime_type}")

        model = "gemini-2.5-flash-image-preview"
        
        # 构建parts列表
        parts = []
        for i, (image_data, mime_type) in enumerate(zip(image_data_list, mime_type_list)):
            parts.append(
                types.Part.from_bytes(
                    mime_type=mime_type,
                    data=base64.b64decode(image_data),
                )
            )
        
        # 添加文本提示
        parts.append(types.Part.from_text(text=clothing_prompt))
        
        contents = [
            types.Content(
                role="user",
                parts=parts,
            ),
        ]
        
        generate_content_config = types.GenerateContentConfig(
            response_modalities=[
                "IMAGE",
                "TEXT",
            ],
        )

        print("正在调用API生成内容...")
        file_index = 0
        
        # 设置重试机制
        import time
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                print(f"正在调用API生成内容... (尝试 {attempt + 1}/{max_retries})")
                
                # 使用非流式API调用，避免数据截断问题
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=generate_content_config,
                )
                
                # 检查响应是否有效
                if (response.candidates is None or 
                    len(response.candidates) == 0 or
                    response.candidates[0].content is None or
                    response.candidates[0].content.parts is None):
                    print("API响应无效：没有候选内容")
                    continue
                
                # 处理响应中的图像数据
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
                        inline_data = part.inline_data
                        data_buffer = inline_data.data
                        
                        # 打印MIME类型信息用于调试
                        print(f"API返回的MIME类型: {inline_data.mime_type}")
                        print(f"原始数据长度: {len(data_buffer)} 字节")
                        
                        # 检查数据格式并正确处理
                        print(f"数据类型: {type(data_buffer)}")
                        
                        # 检查数据是否是字符串（Base64）还是二进制
                        if isinstance(data_buffer, str):
                            print("数据是字符串格式，尝试Base64解码...")
                            try:
                                # 尝试解码Base64数据
                                decoded_data = base64.b64decode(data_buffer)
                                print(f"Base64解码成功: {len(decoded_data)} 字节")
                                
                                # 验证解码后的数据大小是否合理
                                if len(decoded_data) < 1000:  # 如果解码后数据太小，可能有问题
                                    print(f"⚠ 警告：解码后数据大小异常小 ({len(decoded_data)} bytes)")
                                    # 尝试重新编码再解码验证
                                    re_encoded = base64.b64encode(decoded_data).decode('utf-8')
                                    if re_encoded != data_buffer:
                                        print("⚠ 数据完整性检查失败：重新编码后不匹配")
                                        continue
                                
                                data_buffer = decoded_data
                                
                            except Exception as e:
                                print(f"Base64解码失败: {e}")
                                continue
                        else:
                            print("✓ 数据是二进制格式，直接使用")
                            # 数据已经是二进制，直接使用
                        
                        # 根据MIME类型确定正确的文件扩展名
                        if inline_data.mime_type == "image/png":
                            file_extension = ".png"
                        elif inline_data.mime_type == "image/jpeg":
                            file_extension = ".jpg"
                        elif inline_data.mime_type == "image/webp":
                            file_extension = ".webp"
                        else:
                            # 如果无法确定，默认使用.png
                            file_extension = ".png"
                            print(f"未知MIME类型 {inline_data.mime_type}，使用默认扩展名 .png")
                        
                        # 生成输出文件名
                        if output_path.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                            # 如果输出路径已经包含扩展名，直接使用
                            final_output_path = output_path
                        else:
                            # 否则添加扩展名
                            final_output_path = f"{output_path}{file_extension}"
                        
                        # 保存文件
                        self._save_binary_file(final_output_path, data_buffer)
                        print(f"保存图像文件: {final_output_path}")
                        
                        # 验证文件是否有效
                        is_valid, format_info = self._validate_image_file(final_output_path)
                        if is_valid:
                            print(f"✓ {final_output_path} 是有效的{format_info}文件")
                        else:
                            print(f"⚠ {final_output_path} 文件验证失败: {format_info}")
                            
                            # 如果文件验证失败，尝试修复
                            print("🔧 尝试修复损坏的文件...")
                            try:
                                # 读取损坏的文件
                                with open(final_output_path, "rb") as f:
                                    corrupted_data = f.read()
                                
                                # 检查是否是Base64数据被错误写入
                                if len(corrupted_data) < 1000 and isinstance(corrupted_data, bytes):
                                    try:
                                        # 尝试将损坏的数据当作Base64解码
                                        fixed_data = base64.b64decode(corrupted_data)
                                        print(f"修复成功：解码后大小 {len(fixed_data)} bytes")
                                        
                                        # 保存修复后的文件
                                        fixed_path = final_output_path.replace('.png', '_fixed.png')
                                        with open(fixed_path, "wb") as f:
                                            f.write(fixed_data)
                                        
                                        # 验证修复后的文件
                                        is_fixed_valid, fixed_format = self._validate_image_file(fixed_path)
                                        if is_fixed_valid:
                                            print(f"✅ 文件修复成功: {fixed_path}")
                                            # 替换原文件
                                            os.replace(fixed_path, final_output_path)
                                        else:
                                            print(f"❌ 修复后仍无效: {fixed_format}")
                                            
                                    except Exception as fix_e:
                                        print(f"❌ 修复失败: {fix_e}")
                                        
                            except Exception as e:
                                print(f"❌ 修复过程出错: {e}")
                        
                        file_index += 1
                        break  # 只处理第一个图像
                    elif hasattr(part, 'text') and part.text:
                        print(f"文本内容: {part.text}")
                
                # 如果成功处理了图像，跳出重试循环
                if file_index > 0:
                    print(f"图像生成完成，共处理 {file_index} 个图像")
                    return True
                    
            except Exception as e:
                print(f"第 {attempt + 1} 次尝试失败: {e}")
                if attempt < max_retries - 1:
                    print(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    print(f"所有重试都失败了: {e}")
                    return False
        
        return False
