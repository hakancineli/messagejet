import pandas as pd
import os

# 1'den 3500'e kadar olan numaraları oluştur
numbers = list(range(1, 3501))

# Her numarayı 4 haneli formata getir
formatted_numbers = [str(num).zfill(4) for num in numbers]

# DataFrame oluştur
df = pd.DataFrame({
    'Numara': formatted_numbers,
    'Mesaj': ['aktif2'] * len(formatted_numbers)
})

# Excel dosyası olarak kaydet
excel_file = 'aktif2_1-3500.xlsx'
df.to_excel(excel_file, index=False)

print(f"Excel dosyası oluşturuldu: {excel_file}") 