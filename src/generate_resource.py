from PIL import Image, ImageDraw

def create_placeholder_image(path):
    # 创建一个 200x200 的透明图片
    img = Image.new('RGBA', (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 画一个深红色的圆 (胡桃的主色调)
    draw.ellipse((10, 10, 190, 190), fill=(165, 42, 42, 255), outline=(0, 0, 0, 255))
    
    # 画两个眼睛
    draw.ellipse((60, 70, 80, 90), fill=(255, 255, 255, 255))
    draw.ellipse((120, 70, 140, 90), fill=(255, 255, 255, 255))
    
    # 画个嘴巴
    draw.arc((70, 100, 130, 140), start=0, end=180, fill=(0, 0, 0, 255), width=3)
    
    img.save(path)
    print(f"Image saved to {path}")

if __name__ == "__main__":
    create_placeholder_image(r"D:\tools\aiCode\AiPet\code\PetProject\resources\images\hutao.png")

