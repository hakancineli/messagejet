import pandas as pd

# Excel dosyasını oku
df = pd.read_excel('4000.xlsx')

# İlk 10 satırı göster
print("\nİlk 10 satır:")
print(df.head(10))

# Sütun isimlerini göster
print("\nSütun isimleri:")
print(df.columns.tolist()) 