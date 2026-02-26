import os
import sys
import subprocess

def install_requirements():
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Instalare componente...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "--quiet"])

def make_universal_round():
    from PIL import Image, ImageDraw
    
    input_file = "icon.png"
    output_file = "icon_final.png"

    if not os.path.exists(input_file):
        print(f"Eroare: Nu gasesc fisierul {input_file}")
        import time
        time.sleep(3)
        return

    # 1. Deschidem imaginea
    img = Image.open(input_file).convert("RGBA")
    width, height = img.size
    
    # 2. Facem imaginea patrata (centrat) pentru un cerc perfect
    size = min(width, height)
    left = (width - size) // 2
    top = (height - size) // 2
    img = img.crop((left, top, left + size, top + size))
    
    # 3. Cream masca de transparenta
    # 'L' este un mod de imagine pentru umbre de gri (0=transparent, 255=opac)
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    
    # Desenam un cerc alb (255) pe fundalul negru (0) al mastii
    # Folosim o mica ajustare (-1) pentru a nu taia pixelii de pe margine
    draw.ellipse((0, 0, size - 1, size - 1), fill=255)

    # 4. Cream o imagine noua, complet transparenta
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    
    # 5. Lipim imaginea originala peste cea transparenta, folosind masca rotunda
    result.paste(img, (0, 0), mask=mask)

    # 6. Salvare
    result.save(output_file, "PNG")
    print(f"Succes! Iconita rotunda a fost creata: {output_file}")
    
    import time
    time.sleep(2)

if __name__ == "__main__":
    install_requirements()
    make_universal_round()