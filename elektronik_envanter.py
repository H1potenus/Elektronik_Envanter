"""
Elektronik Komponent & Proje Envanter Uygulaması
=================================================
Gereksinimler: pip install customtkinter
Çalıştırma   : python elektronik_envanter.py
Veritabanı   : inventory.db (otomatik oluşturulur)
"""

import customtkinter as ctk
import sqlite3
import csv
import os
from datetime import datetime
from tkinter import messagebox, filedialog
import tkinter as tk

# ─────────────────────────────────────────────────────────────────
# Tema & Renk Paleti
# ─────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

RENK = {
    "bg_ana":       "#1a1a2e",
    "bg_kenar":     "#16213e",
    "bg_kart":      "#0f3460",
    "vurgu":        "#e94560",
    "vurgu2":       "#533483",
    "yesil":        "#2ecc71",
    "sari":         "#f39c12",
    "metin":        "#ecf0f1",
    "metin_soluk":  "#95a5a6",
    "border":       "#2c3e50",
}

DB_DOSYASI = "inventory.db"


# ─────────────────────────────────────────────────────────────────
# Veritabanı Yöneticisi
# ─────────────────────────────────────────────────────────────────
class VeritabaniYonetici:
    """Tüm SQLite işlemlerini yönetir."""

    def __init__(self, db_yolu: str = DB_DOSYASI):
        self.db_yolu = db_yolu
        self.baglanti = sqlite3.connect(self.db_yolu, check_same_thread=False)
        self.baglanti.row_factory = sqlite3.Row
        self.baglanti.execute("PRAGMA foreign_keys = ON")
        self._tablolari_olustur()

    # ── Tablo kurulumu ──────────────────────────────────────────
    def _tablolari_olustur(self):
        cur = self.baglanti.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS kategoriler (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                isim TEXT    NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS komponentler (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                isim      TEXT    NOT NULL,
                deger     TEXT    DEFAULT '',
                kategori  INTEGER REFERENCES kategoriler(id) ON DELETE SET NULL,
                miktar    INTEGER NOT NULL DEFAULT 0,
                konum     TEXT    DEFAULT '',
                notlar    TEXT    DEFAULT '',
                ekleme_tarihi TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS projeler (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                isim    TEXT NOT NULL,
                aciklama TEXT DEFAULT '',
                durum   TEXT DEFAULT 'Aktif',
                tarih   TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS proje_bom (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                proje_id     INTEGER NOT NULL REFERENCES projeler(id) ON DELETE CASCADE,
                komponent_id INTEGER NOT NULL REFERENCES komponentler(id) ON DELETE CASCADE,
                miktar       INTEGER NOT NULL DEFAULT 1,
                dusuruldu    INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS istek_listesi (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                isim  TEXT NOT NULL,
                notlar TEXT DEFAULT '',
                tarih TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        self.baglanti.commit()

        # Varsayılan kategoriler
        varsayilan = [
            "Dirençler", "Kapasitörler", "Bobinler", "Diyotlar",
            "Transistörler", "Entegreler", "Mikrokontrölörler",
            "Sensörler", "Modüller", "Konnektörler", "Mekanik", "Diğer"
        ]
        for kat in varsayilan:
            cur.execute("INSERT OR IGNORE INTO kategoriler (isim) VALUES (?)", (kat,))
        self.baglanti.commit()

    # ── Kategori işlemleri ──────────────────────────────────────
    def kategorileri_getir(self):
        return self.baglanti.execute(
            "SELECT id, isim FROM kategoriler ORDER BY isim"
        ).fetchall()

    def kategori_ekle(self, isim: str):
        try:
            self.baglanti.execute("INSERT INTO kategoriler (isim) VALUES (?)", (isim,))
            self.baglanti.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def kategori_sil(self, kid: int):
        """Kategoriyi siler; bağlı komponentlerin 'kategori' alanı NULL olur (ON DELETE SET NULL)."""
        self.baglanti.execute("DELETE FROM kategoriler WHERE id=?", (kid,))
        self.baglanti.commit()

    def kategori_guncelle(self, kid: int, yeni_isim: str) -> bool:
        """Kategori adını günceller. Eğer isim zaten varsa False döner."""
        try:
            self.baglanti.execute(
                "UPDATE kategoriler SET isim=? WHERE id=?", (yeni_isim, kid)
            )
            self.baglanti.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def komponentleri_kategori_ile_getir(self, kategori_id: int):
        """Belirli bir kategoriye ait komponentleri döner."""
        return self.baglanti.execute("""
            SELECT k.id, k.isim, k.deger, k.miktar, k.konum
            FROM komponentler k
            WHERE k.kategori = ?
            ORDER BY k.isim
        """, (kategori_id,)).fetchall()

    # ── Komponent işlemleri ─────────────────────────────────────
    def komponentleri_getir(self, arama: str = ""):
        sorgu = """
            SELECT k.id, k.isim, k.deger, kat.isim AS kategori,
                   k.miktar, k.konum, k.notlar, k.ekleme_tarihi
            FROM komponentler k
            LEFT JOIN kategoriler kat ON k.kategori = kat.id
            WHERE k.isim LIKE ? OR k.deger LIKE ? OR kat.isim LIKE ?
                  OR k.konum LIKE ? OR k.notlar LIKE ?
            ORDER BY kat.isim, k.isim
        """
        p = f"%{arama}%"
        return self.baglanti.execute(sorgu, (p, p, p, p, p)).fetchall()

    def komponent_ekle(self, isim, deger, kategori_id, miktar, konum, notlar):
        self.baglanti.execute(
            "INSERT INTO komponentler (isim,deger,kategori,miktar,konum,notlar) "
            "VALUES (?,?,?,?,?,?)",
            (isim, deger, kategori_id, miktar, konum, notlar)
        )
        self.baglanti.commit()

    def komponent_guncelle(self, kid, isim, deger, kategori_id, miktar, konum, notlar):
        self.baglanti.execute(
            "UPDATE komponentler SET isim=?,deger=?,kategori=?,miktar=?,konum=?,notlar=? "
            "WHERE id=?",
            (isim, deger, kategori_id, miktar, konum, notlar, kid)
        )
        self.baglanti.commit()

    def komponent_sil(self, kid: int):
        self.baglanti.execute("DELETE FROM komponentler WHERE id=?", (kid,))
        self.baglanti.commit()

    def miktar_guncelle(self, kid: int, yeni_miktar: int):
        self.baglanti.execute(
            "UPDATE komponentler SET miktar=? WHERE id=?", (yeni_miktar, kid)
        )
        self.baglanti.commit()

    def komponent_detay(self, kid: int):
        return self.baglanti.execute(
            "SELECT * FROM komponentler WHERE id=?", (kid,)
        ).fetchone()

    # ── Proje işlemleri ─────────────────────────────────────────
    def projeleri_getir(self):
        return self.baglanti.execute(
            "SELECT * FROM projeler ORDER BY tarih DESC"
        ).fetchall()

    def proje_ekle(self, isim, aciklama):
        cur = self.baglanti.execute(
            "INSERT INTO projeler (isim,aciklama) VALUES (?,?)", (isim, aciklama)
        )
        self.baglanti.commit()
        return cur.lastrowid

    def proje_sil(self, pid: int):
        self.baglanti.execute("DELETE FROM projeler WHERE id=?", (pid,))
        self.baglanti.commit()

    def proje_durum_guncelle(self, pid: int, durum: str):
        self.baglanti.execute(
            "UPDATE projeler SET durum=? WHERE id=?", (durum, pid)
        )
        self.baglanti.commit()

    # ── BOM işlemleri ───────────────────────────────────────────
    def bom_getir(self, proje_id: int):
        return self.baglanti.execute("""
            SELECT pb.id, k.isim, k.deger, kat.isim AS kategori,
                   pb.miktar, k.miktar AS stok, pb.komponent_id, pb.dusuruldu
            FROM proje_bom pb
            JOIN komponentler k ON pb.komponent_id = k.id
            LEFT JOIN kategoriler kat ON k.kategori = kat.id
            WHERE pb.proje_id = ?
            ORDER BY kat.isim, k.isim
        """, (proje_id,)).fetchall()

    def bom_ekle(self, proje_id, komponent_id, miktar):
        # Aynı komponent zaten eklenmiş mi?
        mevcut = self.baglanti.execute(
            "SELECT id, miktar FROM proje_bom WHERE proje_id=? AND komponent_id=?",
            (proje_id, komponent_id)
        ).fetchone()
        if mevcut:
            self.baglanti.execute(
                "UPDATE proje_bom SET miktar=miktar+? WHERE id=?",
                (miktar, mevcut["id"])
            )
        else:
            self.baglanti.execute(
                "INSERT INTO proje_bom (proje_id,komponent_id,miktar) VALUES (?,?,?)",
                (proje_id, komponent_id, miktar)
            )
        self.baglanti.commit()

    def bom_kalemi_sil(self, bom_id: int):
        self.baglanti.execute("DELETE FROM proje_bom WHERE id=?", (bom_id,))
        self.baglanti.commit()

    def stok_dusur(self, bom_id: int):
        """BOM kalemini stoktan düşür."""
        kalem = self.baglanti.execute(
            "SELECT pb.miktar, pb.dusuruldu, pb.komponent_id, k.miktar AS stok "
            "FROM proje_bom pb JOIN komponentler k ON pb.komponent_id=k.id "
            "WHERE pb.id=?", (bom_id,)
        ).fetchone()
        if not kalem:
            return False, "Kalem bulunamadı."
        if kalem["dusuruldu"]:
            return False, "Stok zaten düşürülmüş!"
        if kalem["stok"] < kalem["miktar"]:
            return False, (f"Yetersiz stok! Mevcut: {kalem['stok']}, "
                           f"Gereken: {kalem['miktar']}")
        self.baglanti.execute(
            "UPDATE komponentler SET miktar=miktar-? WHERE id=?",
            (kalem["miktar"], kalem["komponent_id"])
        )
        self.baglanti.execute(
            "UPDATE proje_bom SET dusuruldu=1 WHERE id=?", (bom_id,)
        )
        self.baglanti.commit()
        return True, "Stok başarıyla düşürüldü."

    def stoka_iade(self, bom_id: int):
        """Düşürülmüş stoğu geri ekle."""
        kalem = self.baglanti.execute(
            "SELECT pb.miktar, pb.dusuruldu, pb.komponent_id "
            "FROM proje_bom pb WHERE pb.id=?", (bom_id,)
        ).fetchone()
        if not kalem:
            return False, "Kalem bulunamadı."
        if not kalem["dusuruldu"]:
            return False, "Stok daha önce düşürülmemiş."
        self.baglanti.execute(
            "UPDATE komponentler SET miktar=miktar+? WHERE id=?",
            (kalem["miktar"], kalem["komponent_id"])
        )
        self.baglanti.execute(
            "UPDATE proje_bom SET dusuruldu=0 WHERE id=?", (bom_id,)
        )
        self.baglanti.commit()
        return True, "Stok başarıyla iade edildi."

    # ── İstek listesi işlemleri ─────────────────────────────────
    def istek_listesini_getir(self):
        return self.baglanti.execute(
            "SELECT * FROM istek_listesi ORDER BY tarih DESC"
        ).fetchall()

    def istek_ekle(self, isim, notlar):
        self.baglanti.execute(
            "INSERT INTO istek_listesi (isim,notlar) VALUES (?,?)", (isim, notlar)
        )
        self.baglanti.commit()

    def istek_sil(self, iid: int):
        self.baglanti.execute("DELETE FROM istek_listesi WHERE id=?", (iid,))
        self.baglanti.commit()

    # ── CSV Dışa Aktarma ────────────────────────────────────────
    def csv_aktar(self, dosya_yolu: str) -> int:
        satirlar = self.komponentleri_getir("")
        with open(dosya_yolu, "w", newline="", encoding="utf-8-sig") as f:
            yazar = csv.writer(f)
            yazar.writerow(["ID", "İsim", "Değer/Model", "Kategori",
                            "Miktar", "Konum", "Notlar", "Ekleme Tarihi"])
            for satir in satirlar:
                yazar.writerow(list(satir))
        return len(satirlar)

    def kapat(self):
        self.baglanti.close()


# ─────────────────────────────────────────────────────────────────
# Yardımcı Widget'lar
# ─────────────────────────────────────────────────────────────────
class EtiketliGiris(ctk.CTkFrame):
    """Etiket + giriş alanı birleşimi."""

    def __init__(self, parent, etiket: str, **kwargs):
        super().__init__(parent, fg_color="transparent")
        ctk.CTkLabel(self, text=etiket, font=("Segoe UI", 11),
                     text_color=RENK["metin_soluk"]).pack(anchor="w")
        self.giris = ctk.CTkEntry(self, height=32, **kwargs)
        self.giris.pack(fill="x", pady=(2, 0))

    def get(self):
        return self.giris.get().strip()

    def set(self, deger):
        self.giris.delete(0, "end")
        self.giris.insert(0, str(deger))

    def temizle(self):
        self.giris.delete(0, "end")


class RenkliButon(ctk.CTkButton):
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("corner_radius", 8)
        kwargs.setdefault("height", 34)
        kwargs.setdefault("font", ("Segoe UI", 12, "bold"))
        super().__init__(parent, **kwargs)


# ─────────────────────────────────────────────────────────────────
# Envanter Sekmesi
# ─────────────────────────────────────────────────────────────────
class EnvanterSekmesi(ctk.CTkFrame):
    def __init__(self, parent, db: VeritabaniYonetici):
        super().__init__(parent, fg_color=RENK["bg_ana"])
        self.db = db
        self.secili_id: int | None = None
        self._arayuzu_olustur()
        self.listeyi_yenile()

    def _arayuzu_olustur(self):
        # ── Başlık çubuğu ────────────────────────────────────────
        ust = ctk.CTkFrame(self, fg_color=RENK["bg_kart"], height=52, corner_radius=0)
        ust.pack(fill="x")
        ctk.CTkLabel(ust, text="⚡  Komponent Envanteri",
                     font=("Segoe UI", 16, "bold"),
                     text_color=RENK["vurgu"]).pack(side="left", padx=16, pady=10)

        # Arama + CSV butonu
        sag = ctk.CTkFrame(ust, fg_color="transparent")
        sag.pack(side="right", padx=12, pady=8)

        RenkliButon(sag, text="📤 CSV Aktar", width=120,
                    fg_color=RENK["vurgu2"],
                    hover_color="#6a4c9c",
                    command=self.csv_aktar).pack(side="right", padx=4)

        self.arama_degisken = ctk.StringVar()
        self._arama_timer = None  # Zamanlayıcıyı tutacağımız değişken

        # Direkt listeyi yenilemek yerine gecikmeli fonksiyonu çağırıyoruz
        self.arama_degisken.trace_add("write", self._arama_tetikle)

        ctk.CTkEntry(sag, textvariable=self.arama_degisken,
                     placeholder_text="🔍  Ara...", width=220,
                     height=34).pack(side="right", padx=4)

        # ── Ana içerik alanı ─────────────────────────────────────
        icerik = ctk.CTkFrame(self, fg_color=RENK["bg_ana"])
        icerik.pack(fill="both", expand=True, padx=12, pady=8)
        icerik.columnconfigure(1, weight=1)
        icerik.rowconfigure(0, weight=1)

        # SOL – Hızlı Ekle / Düzenle paneli
        self._sol_panel(icerik)

        # SAĞ – Tablo
        self._sag_panel(icerik)

    def _arama_tetikle(self, *args):
        # Eğer hali hazırda bekleyen bir yenileme varsa onu iptal et
        if self._arama_timer is not None:
            self.after_cancel(self._arama_timer)

        # Kullanıcı tuşa bastıktan 350ms sonra listeyi yenile
        self._arama_timer = self.after(350, self.listeyi_yenile)
    def _sol_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=RENK["bg_kenar"],
                             width=270, corner_radius=12)
        panel.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        panel.pack_propagate(False)

        ctk.CTkLabel(panel, text="➕  Hızlı Ekle / Düzenle",
                     font=("Segoe UI", 13, "bold"),
                     text_color=RENK["vurgu"]).pack(pady=(14, 4), padx=14, anchor="w")

        ic = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        ic.pack(fill="both", expand=True, padx=10, pady=4)

        self.f_isim    = EtiketliGiris(ic, "İsim *")
        self.f_isim.pack(fill="x", pady=3)
        self.f_deger   = EtiketliGiris(ic, "Değer / Model")
        self.f_deger.pack(fill="x", pady=3)

        # Kategori
        ctk.CTkLabel(ic, text="Kategori", font=("Segoe UI", 11),
                     text_color=RENK["metin_soluk"]).pack(anchor="w")
        self.kat_degisken = ctk.StringVar()
        self.kat_combobox = ctk.CTkComboBox(ic, variable=self.kat_degisken,
                                             state="readonly", height=32)
        self.kat_combobox.pack(fill="x", pady=(2, 3))

        self.f_miktar  = EtiketliGiris(ic, "Miktar *")
        self.f_miktar.pack(fill="x", pady=3)
        self.f_konum   = EtiketliGiris(ic, "Konum (örn: Çekmece A1)")
        self.f_konum.pack(fill="x", pady=3)

        ctk.CTkLabel(ic, text="Notlar", font=("Segoe UI", 11),
                     text_color=RENK["metin_soluk"]).pack(anchor="w")
        self.f_notlar = ctk.CTkTextbox(ic, height=60, corner_radius=8)
        self.f_notlar.pack(fill="x", pady=(2, 6))

        # Butonlar
        RenkliButon(ic, text="✅  Kaydet",
                    fg_color=RENK["yesil"], hover_color="#27ae60",
                    command=self.kaydet).pack(fill="x", pady=2)
        RenkliButon(ic, text="🗑️  Sil",
                    fg_color=RENK["vurgu"], hover_color="#c0392b",
                    command=self.sil).pack(fill="x", pady=2)
        RenkliButon(ic, text="🔄  Formu Temizle",
                    fg_color=RENK["bg_kart"], hover_color=RENK["vurgu2"],
                    command=self.formu_temizle).pack(fill="x", pady=2)

        ctk.CTkFrame(ic, height=2, fg_color=RENK["border"]).pack(fill="x", pady=8)

        # Yeni kategori ekleme
        ctk.CTkLabel(ic, text="📁  Yeni Kategori Ekle",
                     font=("Segoe UI", 11, "bold"),
                     text_color=RENK["metin_soluk"]).pack(anchor="w")
        kat_satir = ctk.CTkFrame(ic, fg_color="transparent")
        kat_satir.pack(fill="x", pady=3)
        self.yeni_kat_giris = ctk.CTkEntry(kat_satir, placeholder_text="Kategori adı",
                                            height=32)
        self.yeni_kat_giris.pack(side="left", fill="x", expand=True, padx=(0, 4))
        RenkliButon(kat_satir, text="Ekle", width=60,
                    fg_color=RENK["vurgu2"],
                    command=self.kategori_ekle).pack(side="right")

        self.kategorileri_guncelle()

    def _sag_panel(self, parent):
        cerceve = ctk.CTkFrame(parent, fg_color=RENK["bg_kenar"], corner_radius=12)
        cerceve.grid(row=0, column=1, sticky="nsew")

        # Tablo başlıkları
        sutunlar = ["ID", "İsim", "Değer/Model", "Kategori",
                    "Miktar", "Konum", "Notlar"]
        sutun_genislik = [45, 160, 130, 130, 65, 120, 160]

        # Başlık
        baslik = ctk.CTkFrame(cerceve, fg_color=RENK["bg_kart"],
                               corner_radius=0, height=36)
        baslik.pack(fill="x", padx=0, pady=0)
        for i, (s, g) in enumerate(zip(sutunlar, sutun_genislik)):
            ctk.CTkLabel(baslik, text=s,
                         font=("Segoe UI", 11, "bold"),
                         text_color=RENK["metin"],
                         width=g, anchor="w").pack(side="left", padx=4)

        # Scrollable liste
        self.liste_cerceve = ctk.CTkScrollableFrame(cerceve,
                                                     fg_color="transparent")
        self.liste_cerceve.pack(fill="both", expand=True, padx=4, pady=4)
        self.liste_satirlar: list[ctk.CTkFrame] = []
        self._sutun_genislik = sutun_genislik

        # Alt durum çubuğu
        self.durum_label = ctk.CTkLabel(cerceve,
                                         text="", height=24,
                                         font=("Segoe UI", 10),
                                         text_color=RENK["metin_soluk"])
        self.durum_label.pack(anchor="w", padx=8, pady=2)

    # ── Tablo satırı çiz ────────────────────────────────────────
    def _satir_olustur(self, parent, kalem, bg_rengi: str):
        satir = ctk.CTkFrame(parent, fg_color=bg_rengi, corner_radius=4, height=32)
        satir.pack(fill="x", pady=1)
        satir.pack_propagate(False)

        degerler = [
            str(kalem["id"]),
            kalem["isim"],
            kalem["deger"] or "",
            kalem["kategori"] or "-",
            str(kalem["miktar"]),
            kalem["konum"] or "",
            kalem["notlar"] or "",
        ]
        for deger, genislik in zip(degerler, self._sutun_genislik):
            renk = RENK["metin"]
            if deger.isdigit() and int(deger) == 0:
                renk = RENK["vurgu"]  # sıfır stok kırmızı
            ctk.CTkLabel(satir, text=deger[:22] if len(deger) > 22 else deger,
                         font=("Segoe UI", 11),
                         text_color=renk,
                         width=genislik, anchor="w").pack(side="left", padx=4)

        # Tıklama eventi
        def sec(e, kid=kalem["id"]):
            self.satiri_sec(kid)

        satir.bind("<Button-1>", sec)
        for widget in satir.winfo_children():
            widget.bind("<Button-1>", sec)

        return satir

    def satiri_sec(self, kid: int):
        self.secili_id = kid
        kalem = self.db.komponent_detay(kid)
        if not kalem:
            return
        self.f_isim.set(kalem["isim"])
        self.f_deger.set(kalem["deger"] or "")
        self.f_miktar.set(str(kalem["miktar"]))
        self.f_konum.set(kalem["konum"] or "")
        self.f_notlar.delete("1.0", "end")
        self.f_notlar.insert("1.0", kalem["notlar"] or "")

        # Kategori seç
        katlar = self.db.kategorileri_getir()
        for kat in katlar:
            if kat["id"] == kalem["kategori"]:
                self.kat_degisken.set(kat["isim"])
                break

        self.listeyi_yenile()

    # ── Listeyi yenile ──────────────────────────────────────────
    def listeyi_yenile(self):
        for w in self.liste_cerceve.winfo_children():
            w.destroy()

        arama = self.arama_degisken.get()
        kalemler = self.db.komponentleri_getir(arama)

        for i, kalem in enumerate(kalemler):
            if kalem["id"] == self.secili_id:
                bg = RENK["bg_kart"]
            else:
                bg = "#1e2a3a" if i % 2 == 0 else "#16213e"
            self._satir_olustur(self.liste_cerceve, kalem, bg)

        sayi = len(kalemler)
        toplam = sum(k["miktar"] for k in kalemler)
        sifir = sum(1 for k in kalemler if k["miktar"] == 0)
        self.durum_label.configure(
            text=f"  {sayi} komponent  |  Toplam adet: {toplam}  |  Stok bitti: {sifir}"
        )

    def kategorileri_guncelle(self):
        katlar = self.db.kategorileri_getir()
        isimler = [k["isim"] for k in katlar]
        self.kat_combobox.configure(values=isimler)
        if isimler:
            if not self.kat_degisken.get():
                self.kat_degisken.set(isimler[0])

    def _kategori_id_bul(self, isim: str) -> int | None:
        for kat in self.db.kategorileri_getir():
            if kat["isim"] == isim:
                return kat["id"]
        return None

    # ── Eylemler ────────────────────────────────────────────────
    def kaydet(self):
        isim = self.f_isim.get()
        miktar_str = self.f_miktar.get()
        if not isim:
            messagebox.showwarning("Uyarı", "İsim alanı zorunludur!")
            return
        try:
            miktar = int(miktar_str) if miktar_str else 0
            if miktar < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Uyarı", "Miktar geçerli bir sayı olmalıdır!")
            return

        kat_id = self._kategori_id_bul(self.kat_degisken.get())
        deger  = self.f_deger.get()
        konum  = self.f_konum.get()
        notlar = self.f_notlar.get("1.0", "end").strip()

        if self.secili_id:
            self.db.komponent_guncelle(self.secili_id, isim, deger,
                                        kat_id, miktar, konum, notlar)
            messagebox.showinfo("✅ Başarılı", "Komponent güncellendi.")
        else:
            self.db.komponent_ekle(isim, deger, kat_id, miktar, konum, notlar)
            messagebox.showinfo("✅ Başarılı", "Komponent eklendi.")

        self.formu_temizle()
        self.listeyi_yenile()

    def sil(self):
        if not self.secili_id:
            messagebox.showwarning("Uyarı", "Lütfen bir komponent seçin.")
            return
        if messagebox.askyesno("Sil", "Seçili komponent silinecek. Emin misiniz?"):
            self.db.komponent_sil(self.secili_id)
            self.formu_temizle()
            self.listeyi_yenile()

    def formu_temizle(self):
        self.secili_id = None
        for alan in [self.f_isim, self.f_deger, self.f_miktar, self.f_konum]:
            alan.temizle()
        self.f_notlar.delete("1.0", "end")
        katlar = [k["isim"] for k in self.db.kategorileri_getir()]
        if katlar:
            self.kat_degisken.set(katlar[0])
        self.listeyi_yenile()

    def kategori_ekle(self):
        isim = self.yeni_kat_giris.get().strip()
        if not isim:
            return
        if self.db.kategori_ekle(isim):
            self.yeni_kat_giris.delete(0, "end")
            self.kategorileri_guncelle()
            messagebox.showinfo("✅", f"'{isim}' kategorisi eklendi.")
        else:
            messagebox.showwarning("Uyarı", "Bu kategori zaten mevcut!")

    def csv_aktar(self):
        dosya = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Dosyası", "*.csv")],
            initialfile="envanter_yedek.csv",
            title="CSV Olarak Kaydet"
        )
        if dosya:
            sayi = self.db.csv_aktar(dosya)
            messagebox.showinfo("✅ Başarılı",
                                f"{sayi} komponent '{dosya}' dosyasına aktarıldı.")


# ─────────────────────────────────────────────────────────────────
# Projeler Sekmesi
# ─────────────────────────────────────────────────────────────────
class ProjelerSekmesi(ctk.CTkFrame):
    def __init__(self, parent, db: VeritabaniYonetici):
        super().__init__(parent, fg_color=RENK["bg_ana"])
        self.db = db
        self.secili_proje_id: int | None = None
        self._arayuzu_olustur()
        self.projeleri_yenile()

    def _arayuzu_olustur(self):
        # ── Başlık ───────────────────────────────────────────────
        ust = ctk.CTkFrame(self, fg_color=RENK["bg_kart"], height=52, corner_radius=0)
        ust.pack(fill="x")
        ctk.CTkLabel(ust, text="🗂️  Proje Yönetimi & Malzeme Listesi (BOM)",
                     font=("Segoe UI", 16, "bold"),
                     text_color=RENK["vurgu"]).pack(side="left", padx=16, pady=10)

        # ── Sol: Proje listesi ───────────────────────────────────
        ana = ctk.CTkFrame(self, fg_color=RENK["bg_ana"])
        ana.pack(fill="both", expand=True, padx=12, pady=8)
        ana.columnconfigure(1, weight=1)
        ana.rowconfigure(0, weight=1)

        # Sol panel
        sol = ctk.CTkFrame(ana, fg_color=RENK["bg_kenar"],
                            width=240, corner_radius=12)
        sol.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        sol.pack_propagate(False)

        ctk.CTkLabel(sol, text="Projeler",
                     font=("Segoe UI", 13, "bold"),
                     text_color=RENK["vurgu"]).pack(pady=(12, 4), padx=12, anchor="w")

        # Yeni proje formu
        form = ctk.CTkFrame(sol, fg_color=RENK["bg_kart"], corner_radius=8)
        form.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(form, text="Proje Adı *", font=("Segoe UI", 10),
                     text_color=RENK["metin_soluk"]).pack(anchor="w", padx=8, pady=(6, 0))
        self.proje_isim_giris = ctk.CTkEntry(form, height=30)
        self.proje_isim_giris.pack(fill="x", padx=8, pady=(2, 4))
        ctk.CTkLabel(form, text="Açıklama", font=("Segoe UI", 10),
                     text_color=RENK["metin_soluk"]).pack(anchor="w", padx=8)
        self.proje_aciklama_giris = ctk.CTkEntry(form, height=30)
        self.proje_aciklama_giris.pack(fill="x", padx=8, pady=(2, 4))
        RenkliButon(form, text="➕  Proje Oluştur",
                    fg_color=RENK["yesil"], hover_color="#27ae60",
                    command=self.proje_olustur).pack(fill="x", padx=8, pady=(0, 8))

        # Proje scroll listesi
        self.proje_listesi = ctk.CTkScrollableFrame(sol, fg_color="transparent")
        self.proje_listesi.pack(fill="both", expand=True, padx=4, pady=4)

        # ── Sağ: BOM paneli ──────────────────────────────────────
        sag = ctk.CTkFrame(ana, fg_color=RENK["bg_kenar"], corner_radius=12)
        sag.grid(row=0, column=1, sticky="nsew")

        # BOM başlığı
        bom_ust = ctk.CTkFrame(sag, fg_color=RENK["bg_kart"],
                                height=44, corner_radius=0)
        bom_ust.pack(fill="x")
        self.bom_baslik = ctk.CTkLabel(bom_ust,
                                        text="← Bir proje seçin",
                                        font=("Segoe UI", 13, "bold"),
                                        text_color=RENK["metin_soluk"])
        self.bom_baslik.pack(side="left", padx=12, pady=8)

        # Komponent ekleme satırı
        ekle_satir = ctk.CTkFrame(sag, fg_color=RENK["bg_kart"], corner_radius=0)
        ekle_satir.pack(fill="x", padx=0, pady=0)

        ctk.CTkLabel(ekle_satir, text="Komponent:",
                     font=("Segoe UI", 11),
                     text_color=RENK["metin_soluk"]).pack(side="left", padx=(12, 4))
        self.bom_komp_degisken = ctk.StringVar()
        self.bom_komp_combo = ctk.CTkComboBox(ekle_satir,
                                               variable=self.bom_komp_degisken,
                                               state="readonly",
                                               width=220, height=30)
        self.bom_komp_combo.pack(side="left", padx=4, pady=6)

        ctk.CTkLabel(ekle_satir, text="Adet:",
                     font=("Segoe UI", 11),
                     text_color=RENK["metin_soluk"]).pack(side="left", padx=(8, 4))
        self.bom_miktar_giris = ctk.CTkEntry(ekle_satir, width=60, height=30)
        self.bom_miktar_giris.insert(0, "1")
        self.bom_miktar_giris.pack(side="left", padx=4)

        RenkliButon(ekle_satir, text="BOM'a Ekle",
                    fg_color=RENK["vurgu2"],
                    command=self.boma_ekle).pack(side="left", padx=8)

        # BOM tablosu
        bom_tablo_cerceve = ctk.CTkFrame(sag, fg_color="transparent")
        bom_tablo_cerceve.pack(fill="both", expand=True, padx=8, pady=4)

        bom_basliklar = ctk.CTkFrame(bom_tablo_cerceve,
                                      fg_color=RENK["bg_kart"],
                                      height=32, corner_radius=0)
        bom_basliklar.pack(fill="x")
        for b_isim, b_gen in [("İsim", 160), ("Model", 110), ("Kategori", 110),
                               ("Adet", 60), ("Stok", 60), ("İşlemler", 200)]:
            ctk.CTkLabel(bom_basliklar, text=b_isim,
                         font=("Segoe UI", 11, "bold"),
                         text_color=RENK["metin"],
                         width=b_gen, anchor="w").pack(side="left", padx=4)

        self.bom_liste = ctk.CTkScrollableFrame(bom_tablo_cerceve,
                                                 fg_color="transparent")
        self.bom_liste.pack(fill="both", expand=True)

        self.bom_komponentleri_guncelle()

    # ── Proje işlemleri ─────────────────────────────────────────
    def projeleri_yenile(self):
        for w in self.proje_listesi.winfo_children():
            w.destroy()
        projeler = self.db.projeleri_getir()
        for proje in projeler:
            bg = RENK["bg_kart"] if proje["id"] == self.secili_proje_id else RENK["bg_kenar"]
            satir = ctk.CTkFrame(self.proje_listesi, fg_color=bg,
                                  corner_radius=8, height=52)
            satir.pack(fill="x", pady=2, padx=2)
            satir.pack_propagate(False)

            durum_renk = RENK["yesil"] if proje["durum"] == "Aktif" else RENK["sari"]
            icerik = ctk.CTkFrame(satir, fg_color="transparent")
            icerik.pack(fill="both", expand=True, padx=8, pady=4)

            ctk.CTkLabel(icerik, text=proje["isim"],
                         font=("Segoe UI", 12, "bold"),
                         text_color=RENK["metin"],
                         anchor="w").pack(fill="x")

            alt = ctk.CTkFrame(icerik, fg_color="transparent")
            alt.pack(fill="x")
            ctk.CTkLabel(alt,
                         text=f"● {proje['durum']}",
                         font=("Segoe UI", 10),
                         text_color=durum_renk).pack(side="left")
            ctk.CTkLabel(alt,
                         text=f" | {proje['tarih'][:10]}",
                         font=("Segoe UI", 10),
                         text_color=RENK["metin_soluk"]).pack(side="left")

            def proje_sec(e=None, pid=proje["id"], pisim=proje["isim"]):
                self.secili_proje_id = pid
                self.bom_baslik.configure(
                    text=f"📋  BOM: {pisim}",
                    text_color=RENK["vurgu"]
                )
                self.projeleri_yenile()
                self.bom_yenile()

            satir.bind("<Button-1>", proje_sec)
            for w in icerik.winfo_children() + alt.winfo_children():
                w.bind("<Button-1>", proje_sec)

            # Sil butonu
            sil_btn = ctk.CTkButton(satir, text="🗑", width=28, height=24,
                                     fg_color=RENK["vurgu"],
                                     font=("Segoe UI", 11),
                                     command=lambda pid=proje["id"]: self.proje_sil(pid))
            sil_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-4, y=4)

    def proje_olustur(self):
        isim = self.proje_isim_giris.get().strip()
        if not isim:
            messagebox.showwarning("Uyarı", "Proje adı zorunludur!")
            return
        aciklama = self.proje_aciklama_giris.get().strip()
        pid = self.db.proje_ekle(isim, aciklama)
        self.proje_isim_giris.delete(0, "end")
        self.proje_aciklama_giris.delete(0, "end")
        self.secili_proje_id = pid
        self.bom_baslik.configure(text=f"📋  BOM: {isim}",
                                   text_color=RENK["vurgu"])
        self.projeleri_yenile()
        self.bom_yenile()

    def proje_sil(self, pid: int):
        if messagebox.askyesno("Sil",
                               "Proje ve tüm BOM kalemleri silinecek. Emin misiniz?"):
            self.db.proje_sil(pid)
            if self.secili_proje_id == pid:
                self.secili_proje_id = None
                self.bom_baslik.configure(text="← Bir proje seçin",
                                           text_color=RENK["metin_soluk"])
                self.bom_yenile()
            self.projeleri_yenile()

    # ── BOM işlemleri ────────────────────────────────────────────
    def bom_komponentleri_guncelle(self):
        komp = self.db.komponentleri_getir("")
        isimler = [f"{k['isim']} ({k['deger'] or '-'})  [{k['id']}]" for k in komp]
        self.bom_komp_combo.configure(values=isimler)
        if isimler:
            self.bom_komp_degisken.set(isimler[0])
        self._bom_komp_listesi = komp

    def _komp_id_al(self) -> int | None:
        secim = self.bom_komp_degisken.get()
        try:
            kid = int(secim.split("[")[-1].rstrip("]"))
            return kid
        except (ValueError, IndexError):
            return None

    def boma_ekle(self):
        if not self.secili_proje_id:
            messagebox.showwarning("Uyarı", "Önce bir proje seçin!")
            return
        kid = self._komp_id_al()
        if not kid:
            messagebox.showwarning("Uyarı", "Geçersiz komponent seçimi!")
            return
        try:
            miktar = int(self.bom_miktar_giris.get())
            if miktar <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Uyarı", "Geçerli bir adet girin!")
            return
        self.db.bom_ekle(self.secili_proje_id, kid, miktar)
        self.bom_miktar_giris.delete(0, "end")
        self.bom_miktar_giris.insert(0, "1")
        self.bom_yenile()

    def bom_yenile(self):
        for w in self.bom_liste.winfo_children():
            w.destroy()
        if not self.secili_proje_id:
            return

        kalemler = self.db.bom_getir(self.secili_proje_id)
        for i, kalem in enumerate(kalemler):
            bg = "#1e2a3a" if i % 2 == 0 else "#16213e"
            satir = ctk.CTkFrame(self.bom_liste, fg_color=bg,
                                  corner_radius=4, height=34)
            satir.pack(fill="x", pady=1)
            satir.pack_propagate(False)

            stok_renk = RENK["vurgu"] if kalem["stok"] < kalem["miktar"] else RENK["metin"]

            for metin, genislik in [
                (kalem["isim"][:22], 160),
                (kalem["deger"] or "-", 110),
                (kalem["kategori"] or "-", 110),
                (str(kalem["miktar"]), 60),
                (str(kalem["stok"]), 60),
            ]:
                r = stok_renk if genislik == 60 and metin == str(kalem["stok"]) else RENK["metin"]
                ctk.CTkLabel(satir, text=metin,
                             font=("Segoe UI", 11),
                             text_color=r,
                             width=genislik, anchor="w").pack(side="left", padx=4)

            # İşlem butonları
            btn_cerceve = ctk.CTkFrame(satir, fg_color="transparent")
            btn_cerceve.pack(side="left", padx=2)

            if not kalem["dusuruldu"]:
                ctk.CTkButton(btn_cerceve, text="⬇ Stoktan Düş",
                              width=110, height=24,
                              fg_color=RENK["vurgu"], hover_color="#c0392b",
                              font=("Segoe UI", 10, "bold"),
                              command=lambda bid=kalem["id"]: self.stok_dusur(bid)
                              ).pack(side="left", padx=2)
            else:
                ctk.CTkButton(btn_cerceve, text="↩ İade Et",
                              width=90, height=24,
                              fg_color=RENK["sari"], hover_color="#d68910",
                              font=("Segoe UI", 10, "bold"),
                              command=lambda bid=kalem["id"]: self.stoka_iade(bid)
                              ).pack(side="left", padx=2)
                ctk.CTkLabel(btn_cerceve, text="✓ Düşürüldü",
                             font=("Segoe UI", 10),
                             text_color=RENK["yesil"]).pack(side="left", padx=2)

            ctk.CTkButton(btn_cerceve, text="✕",
                          width=26, height=24,
                          fg_color=RENK["bg_kart"], hover_color=RENK["vurgu"],
                          font=("Segoe UI", 11, "bold"),
                          command=lambda bid=kalem["id"]: self.bom_kalemi_sil(bid)
                          ).pack(side="left", padx=2)

    def stok_dusur(self, bom_id: int):
        basarili, mesaj = self.db.stok_dusur(bom_id)
        if basarili:
            messagebox.showinfo("✅ Başarılı", mesaj)
        else:
            messagebox.showwarning("⚠️ Hata", mesaj)
        self.bom_yenile()

    def stoka_iade(self, bom_id: int):
        basarili, mesaj = self.db.stoka_iade(bom_id)
        if basarili:
            messagebox.showinfo("✅ Başarılı", mesaj)
        else:
            messagebox.showwarning("⚠️ Hata", mesaj)
        self.bom_yenile()

    def bom_kalemi_sil(self, bom_id: int):
        if messagebox.askyesno("Sil", "Bu BOM kalemi silinecek. Emin misiniz?"):
            self.db.bom_kalemi_sil(bom_id)
            self.bom_yenile()


# ─────────────────────────────────────────────────────────────────
# İstek Listesi Sekmesi
# ─────────────────────────────────────────────────────────────────
class IstekListesiSekmesi(ctk.CTkFrame):
    def __init__(self, parent, db: VeritabaniYonetici):
        super().__init__(parent, fg_color=RENK["bg_ana"])
        self.db = db
        self._arayuzu_olustur()
        self.listeyi_yenile()

    def _arayuzu_olustur(self):
        # Başlık
        ust = ctk.CTkFrame(self, fg_color=RENK["bg_kart"], height=52, corner_radius=0)
        ust.pack(fill="x")
        ctk.CTkLabel(ust, text="🛒  İstek Listesi (Alınacaklar)",
                     font=("Segoe UI", 16, "bold"),
                     text_color=RENK["vurgu"]).pack(side="left", padx=16, pady=10)

        # Ana alan
        ana = ctk.CTkFrame(self, fg_color=RENK["bg_ana"])
        ana.pack(fill="both", expand=True, padx=12, pady=8)
        ana.columnconfigure(1, weight=1)
        ana.rowconfigure(0, weight=1)

        # Ekleme paneli (sol)
        ekle = ctk.CTkFrame(ana, fg_color=RENK["bg_kenar"],
                             width=260, corner_radius=12)
        ekle.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        ekle.pack_propagate(False)

        ctk.CTkLabel(ekle, text="Yeni Öğe Ekle",
                     font=("Segoe UI", 13, "bold"),
                     text_color=RENK["vurgu"]).pack(pady=(12, 4), padx=12, anchor="w")

        ic = ctk.CTkFrame(ekle, fg_color="transparent")
        ic.pack(fill="x", padx=10)

        ctk.CTkLabel(ic, text="Komponent / Ürün Adı *",
                     font=("Segoe UI", 11),
                     text_color=RENK["metin_soluk"]).pack(anchor="w")
        self.istek_isim = ctk.CTkEntry(ic, height=32,
                                        placeholder_text="örn: 100nF MLCC SMD 0603")
        self.istek_isim.pack(fill="x", pady=(2, 6))

        ctk.CTkLabel(ic, text="Notlar / Link",
                     font=("Segoe UI", 11),
                     text_color=RENK["metin_soluk"]).pack(anchor="w")
        self.istek_notlar = ctk.CTkTextbox(ic, height=80, corner_radius=8)
        self.istek_notlar.pack(fill="x", pady=(2, 8))

        RenkliButon(ic, text="➕  Listeye Ekle",
                    fg_color=RENK["yesil"], hover_color="#27ae60",
                    command=self.ekle).pack(fill="x", pady=4)

        # Liste (sağ)
        sag = ctk.CTkFrame(ana, fg_color=RENK["bg_kenar"], corner_radius=12)
        sag.grid(row=0, column=1, sticky="nsew")

        baslik_satir = ctk.CTkFrame(sag, fg_color=RENK["bg_kart"],
                                     height=36, corner_radius=0)
        baslik_satir.pack(fill="x")
        for b, g in [("ID", 45), ("İsim / Ürün", 280), ("Notlar", 300),
                     ("Tarih", 130), ("Sil", 60)]:
            ctk.CTkLabel(baslik_satir, text=b,
                         font=("Segoe UI", 11, "bold"),
                         text_color=RENK["metin"],
                         width=g, anchor="w").pack(side="left", padx=4)

        self.liste_alan = ctk.CTkScrollableFrame(sag, fg_color="transparent")
        self.liste_alan.pack(fill="both", expand=True, padx=4, pady=4)

        self.adet_label = ctk.CTkLabel(sag, text="",
                                        font=("Segoe UI", 10),
                                        text_color=RENK["metin_soluk"])
        self.adet_label.pack(anchor="w", padx=8, pady=2)

    def listeyi_yenile(self):
        for w in self.liste_alan.winfo_children():
            w.destroy()
        kalemler = self.db.istek_listesini_getir()
        for i, kalem in enumerate(kalemler):
            bg = "#1e2a3a" if i % 2 == 0 else "#16213e"
            satir = ctk.CTkFrame(self.liste_alan, fg_color=bg,
                                  corner_radius=4, height=34)
            satir.pack(fill="x", pady=1)
            satir.pack_propagate(False)
            for metin, genislik in [
                (str(kalem["id"]), 45),
                (kalem["isim"][:35], 280),
                ((kalem["notlar"] or "")[:40], 300),
                (kalem["tarih"][:10], 130),
            ]:
                ctk.CTkLabel(satir, text=metin,
                             font=("Segoe UI", 11),
                             text_color=RENK["metin"],
                             width=genislik, anchor="w").pack(side="left", padx=4)

            ctk.CTkButton(satir, text="🗑", width=40, height=24,
                          fg_color=RENK["vurgu"], hover_color="#c0392b",
                          font=("Segoe UI", 12),
                          command=lambda iid=kalem["id"]: self.sil(iid)
                          ).pack(side="left", padx=4)

        self.adet_label.configure(text=f"  Toplam: {len(kalemler)} öğe")

    def ekle(self):
        isim = self.istek_isim.get().strip()
        if not isim:
            messagebox.showwarning("Uyarı", "İsim alanı zorunludur!")
            return
        notlar = self.istek_notlar.get("1.0", "end").strip()
        self.db.istek_ekle(isim, notlar)
        self.istek_isim.delete(0, "end")
        self.istek_notlar.delete("1.0", "end")
        self.listeyi_yenile()

    def sil(self, iid: int):
        if messagebox.askyesno("Sil", "Bu öğe listeden silinecek. Emin misiniz?"):
            self.db.istek_sil(iid)
            self.listeyi_yenile()



# ─────────────────────────────────────────────────────────────────
# Kategori Yönetim Sekmesi
# ─────────────────────────────────────────────────────────────────
class KategoriYonetimSekmesi(ctk.CTkFrame):
    """
    Kategori yönetim ekranı.

    Sol Panel  → Mevcut kategorilerin listesi; her satırda Düzenle ve Sil butonu.
    Sağ Panel  → Seçilen kategoriye ait komponentlerin tablosu
                 (İsim, Değer/Model, Miktar, Konum).

    Güvenli silme: Kategori silindiğinde bağlı komponentler
    silinmez; 'kategori' alanları NULL olur (ON DELETE SET NULL).
    """

    def __init__(self, parent, db: VeritabaniYonetici,
                 envanter_sekmesi: "EnvanterSekmesi"):
        super().__init__(parent, fg_color=RENK["bg_ana"])
        self.db = db
        # Envanter sekmesine referans – kategori değişimlerinde ComboBox'ı günceller
        self.envanter_sekmesi = envanter_sekmesi

        # Seçili kategori (id, isim)
        self._secili_kat_id: int | None = None
        self._secili_kat_isim: str = ""

        self._arayuzu_olustur()
        self.listeyi_yenile()

    # ──────────────────────────────────────────────────────────────
    # Arayüz Kurulumu
    # ──────────────────────────────────────────────────────────────
    def _arayuzu_olustur(self):
        # ── Başlık çubuğu ─────────────────────────────────────────
        ust = ctk.CTkFrame(self, fg_color=RENK["bg_kart"],
                           height=52, corner_radius=0)
        ust.pack(fill="x")
        ctk.CTkLabel(
            ust, text="📁  Kategori Yönetimi",
            font=("Segoe UI", 16, "bold"),
            text_color=RENK["vurgu"]
        ).pack(side="left", padx=16, pady=10)

        # ── Ana içerik (sol + sağ) ────────────────────────────────
        ana = ctk.CTkFrame(self, fg_color=RENK["bg_ana"])
        ana.pack(fill="both", expand=True, padx=12, pady=8)
        ana.columnconfigure(1, weight=1)
        ana.rowconfigure(0, weight=1)

        # SOL PANEL ─ Kategori listesi + yeni kategori ekleme
        self._sol_panel(ana)

        # SAĞ PANEL ─ Seçili kategorinin komponent tablosu
        self._sag_panel(ana)

    # ── Sol Panel ─────────────────────────────────────────────────
    def _sol_panel(self, parent):
        sol = ctk.CTkFrame(parent, fg_color=RENK["bg_kenar"],
                           width=280, corner_radius=12)
        sol.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        sol.pack_propagate(False)

        ctk.CTkLabel(
            sol, text="Kategoriler",
            font=("Segoe UI", 13, "bold"),
            text_color=RENK["vurgu"]
        ).pack(pady=(14, 4), padx=14, anchor="w")

        # ── Yeni kategori ekleme ──────────────────────────────────
        ekle_cerceve = ctk.CTkFrame(sol, fg_color=RENK["bg_kart"], corner_radius=8)
        ekle_cerceve.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkLabel(
            ekle_cerceve, text="Yeni Kategori",
            font=("Segoe UI", 11, "bold"),
            text_color=RENK["metin_soluk"]
        ).pack(anchor="w", padx=10, pady=(8, 2))

        satir = ctk.CTkFrame(ekle_cerceve, fg_color="transparent")
        satir.pack(fill="x", padx=10, pady=(0, 8))

        self.yeni_kat_giris = ctk.CTkEntry(
            satir, placeholder_text="Kategori adı...", height=32
        )
        self.yeni_kat_giris.pack(side="left", fill="x", expand=True, padx=(0, 6))
        # Enter tuşuna da bağla
        self.yeni_kat_giris.bind("<Return>", lambda e: self.kategori_ekle())

        RenkliButon(
            satir, text="Ekle", width=60,
            fg_color=RENK["yesil"], hover_color="#27ae60",
            command=self.kategori_ekle
        ).pack(side="right")

        # ── Scrollable kategori listesi ───────────────────────────
        self.kat_liste_alan = ctk.CTkScrollableFrame(
            sol, fg_color="transparent"
        )
        self.kat_liste_alan.pack(fill="both", expand=True, padx=6, pady=4)

        # Alt adet bilgisi
        self.kat_adet_label = ctk.CTkLabel(
            sol, text="",
            font=("Segoe UI", 10),
            text_color=RENK["metin_soluk"]
        )
        self.kat_adet_label.pack(anchor="w", padx=10, pady=(0, 6))

    # ── Sağ Panel ─────────────────────────────────────────────────
    def _sag_panel(self, parent):
        sag = ctk.CTkFrame(parent, fg_color=RENK["bg_kenar"], corner_radius=12)
        sag.grid(row=0, column=1, sticky="nsew")

        # Başlık
        sag_ust = ctk.CTkFrame(sag, fg_color=RENK["bg_kart"],
                               height=44, corner_radius=0)
        sag_ust.pack(fill="x")

        self.sag_baslik = ctk.CTkLabel(
            sag_ust,
            text="← Bir kategori seçin",
            font=("Segoe UI", 13, "bold"),
            text_color=RENK["metin_soluk"]
        )
        self.sag_baslik.pack(side="left", padx=12, pady=8)

        # Komponent sayısı rozeti
        self.komp_sayi_label = ctk.CTkLabel(
            sag_ust, text="",
            font=("Segoe UI", 11),
            text_color=RENK["metin_soluk"]
        )
        self.komp_sayi_label.pack(side="right", padx=12, pady=8)

        # Tablo başlıkları
        baslik_satir = ctk.CTkFrame(sag, fg_color=RENK["bg_kart"],
                                    height=34, corner_radius=0)
        baslik_satir.pack(fill="x")
        for b_isim, b_gen in [
            ("ID", 50), ("İsim", 200), ("Değer / Model", 160),
            ("Miktar", 80), ("Konum", 160)
        ]:
            ctk.CTkLabel(
                baslik_satir, text=b_isim,
                font=("Segoe UI", 11, "bold"),
                text_color=RENK["metin"],
                width=b_gen, anchor="w"
            ).pack(side="left", padx=4)

        # Scrollable tablo
        self.komp_liste_alan = ctk.CTkScrollableFrame(
            sag, fg_color="transparent"
        )
        self.komp_liste_alan.pack(fill="both", expand=True, padx=4, pady=4)

        # Alt bilgi
        self.komp_durum_label = ctk.CTkLabel(
            sag, text="",
            font=("Segoe UI", 10),
            text_color=RENK["metin_soluk"]
        )
        self.komp_durum_label.pack(anchor="w", padx=10, pady=(0, 4))

    # ──────────────────────────────────────────────────────────────
    # Kategori listesini yenile (Sol Panel)
    # ──────────────────────────────────────────────────────────────
    def listeyi_yenile(self):
        """Sol paneldeki kategori listesini veritabanından çekip yeniden çizer."""
        # Mevcut satırları temizle
        for w in self.kat_liste_alan.winfo_children():
            w.destroy()

        kategoriler = self.db.kategorileri_getir()

        for i, kat in enumerate(kategoriler):
            bg = "#1e2a3a" if i % 2 == 0 else "#16213e"
            # Seçili ise farklı renk
            if kat["id"] == self._secili_kat_id:
                bg = RENK["bg_kart"]

            satir = ctk.CTkFrame(
                self.kat_liste_alan, fg_color=bg,
                corner_radius=6, height=38
            )
            satir.pack(fill="x", pady=2)
            satir.pack_propagate(False)

            # Kategori isim etiketi (tıklanabilir)
            isim_label = ctk.CTkLabel(
                satir, text=kat["isim"],
                font=("Segoe UI", 12),
                text_color=RENK["vurgu"] if kat["id"] == self._secili_kat_id
                           else RENK["metin"],
                anchor="w"
            )
            isim_label.pack(side="left", padx=10, fill="x", expand=True)

            # Düzenle butonu
            duz_btn = ctk.CTkButton(
                satir, text="✏️", width=32, height=26,
                fg_color=RENK["vurgu2"], hover_color="#6a4c9c",
                font=("Segoe UI", 12),
                command=lambda kid=kat["id"], kisim=kat["isim"]:
                    self.kategori_duzenle(kid, kisim)
            )
            duz_btn.pack(side="right", padx=(2, 6))

            # Sil butonu
            sil_btn = ctk.CTkButton(
                satir, text="🗑", width=32, height=26,
                fg_color=RENK["vurgu"], hover_color="#c0392b",
                font=("Segoe UI", 12),
                command=lambda kid=kat["id"], kisim=kat["isim"]:
                    self.kategori_sil(kid, kisim)
            )
            sil_btn.pack(side="right", padx=(2, 2))

            # Satıra tıklanınca sağ paneli güncelle
            def sec_kat(e=None, kid=kat["id"], kisim=kat["isim"]):
                self._secili_kat_id   = kid
                self._secili_kat_isim = kisim
                self.listeyi_yenile()        # seçili satırı vurgula
                self.komp_listesini_yenile() # sağ paneli doldur

            satir.bind("<Button-1>", sec_kat)
            isim_label.bind("<Button-1>", sec_kat)

        self.kat_adet_label.configure(text=f"  Toplam: {len(kategoriler)} kategori")

    # ──────────────────────────────────────────────────────────────
    # Komponent tablosunu yenile (Sağ Panel)
    # ──────────────────────────────────────────────────────────────
    def komp_listesini_yenile(self):
        """Seçili kategoriye ait komponentleri sağ panelde gösterir."""
        for w in self.komp_liste_alan.winfo_children():
            w.destroy()

        if self._secili_kat_id is None:
            self.sag_baslik.configure(
                text="← Bir kategori seçin",
                text_color=RENK["metin_soluk"]
            )
            self.komp_sayi_label.configure(text="")
            self.komp_durum_label.configure(text="")
            return

        self.sag_baslik.configure(
            text=f"📦  {self._secili_kat_isim}  –  Komponentler",
            text_color=RENK["vurgu"]
        )

        komponentler = self.db.komponentleri_kategori_ile_getir(self._secili_kat_id)

        for i, komp in enumerate(komponentler):
            bg = "#1e2a3a" if i % 2 == 0 else "#16213e"
            satir = ctk.CTkFrame(
                self.komp_liste_alan, fg_color=bg,
                corner_radius=4, height=32
            )
            satir.pack(fill="x", pady=1)
            satir.pack_propagate(False)

            miktar_renk = RENK["vurgu"] if komp["miktar"] == 0 else RENK["metin"]

            for metin, genislik, renk in [
                (str(komp["id"]),         50,  RENK["metin_soluk"]),
                (komp["isim"][:28],       200, RENK["metin"]),
                ((komp["deger"] or "-")[:20], 160, RENK["metin_soluk"]),
                (str(komp["miktar"]),     80,  miktar_renk),
                ((komp["konum"] or "-")[:20], 160, RENK["metin_soluk"]),
            ]:
                ctk.CTkLabel(
                    satir, text=metin,
                    font=("Segoe UI", 11),
                    text_color=renk,
                    width=genislik, anchor="w"
                ).pack(side="left", padx=4)

        toplam_miktar = sum(k["miktar"] for k in komponentler)
        sifir_stok    = sum(1 for k in komponentler if k["miktar"] == 0)

        self.komp_sayi_label.configure(
            text=f"{len(komponentler)} komponent"
        )
        self.komp_durum_label.configure(
            text=(f"  {len(komponentler)} komponent  |  "
                  f"Toplam adet: {toplam_miktar}  |  "
                  f"Stok bitti: {sifir_stok}")
        )

    # ──────────────────────────────────────────────────────────────
    # Eylemler
    # ──────────────────────────────────────────────────────────────
    def kategori_ekle(self):
        """Yeni bir kategori oluşturur ve listeyi yeniler."""
        isim = self.yeni_kat_giris.get().strip()
        if not isim:
            messagebox.showwarning("Uyarı", "Kategori adı boş olamaz!")
            return
        if self.db.kategori_ekle(isim):
            self.yeni_kat_giris.delete(0, "end")
            self.listeyi_yenile()
            # Envanter sekmesindeki ComboBox'ı da güncelle
            self.envanter_sekmesi.kategorileri_guncelle()
            messagebox.showinfo("✅ Başarılı", f"'{isim}' kategorisi eklendi.")
        else:
            messagebox.showwarning("Uyarı", "Bu isimde bir kategori zaten mevcut!")

    def kategori_duzenle(self, kid: int, mevcut_isim: str):
        """
        Seçili kategorinin adını değiştirir.
        CTkInputDialog ile kullanıcıdan yeni isim alınır.
        Veritabanı + Envanter sekmesi ComboBox'ı anında güncellenir.
        """
        dialog = ctk.CTkInputDialog(
            text=f"'{mevcut_isim}' kategorisinin yeni adını girin:",
            title="Kategoriyi Düzenle"
        )
        yeni_isim = dialog.get_input()

        if yeni_isim is None:          # Kullanıcı iptal etti
            return
        yeni_isim = yeni_isim.strip()
        if not yeni_isim:
            messagebox.showwarning("Uyarı", "Kategori adı boş olamaz!")
            return
        if yeni_isim == mevcut_isim:
            return                     # Değişiklik yok

        if self.db.kategori_guncelle(kid, yeni_isim):
            # Seçili kategori değiştirildiyse başlığı güncelle
            if self._secili_kat_id == kid:
                self._secili_kat_isim = yeni_isim
            self.listeyi_yenile()
            self.komp_listesini_yenile()
            # Envanter sekmesindeki ComboBox'ı güncelle
            self.envanter_sekmesi.kategorileri_guncelle()
            messagebox.showinfo(
                "✅ Başarılı",
                f"Kategori '{mevcut_isim}' → '{yeni_isim}' olarak yeniden adlandırıldı."
            )
        else:
            messagebox.showwarning(
                "Uyarı", f"'{yeni_isim}' adında bir kategori zaten mevcut!"
            )

    def kategori_sil(self, kid: int, isim: str):
        """
        Kategoriyi siler.
        Bağlı komponentler silinmez; kategori referansları NULL olur.
        """
        onay = messagebox.askyesno(
            "Kategoriyi Sil",
            f"'{isim}' kategorisi silinecek.\n\n"
            "Bu kategorideki komponentler SİLİNMEZ;\n"
            "yalnızca kategori atamaları kaldırılır.\n\n"
            "Devam etmek istiyor musunuz?"
        )
        if not onay:
            return

        self.db.kategori_sil(kid)

        # Seçili kategori silindiyse sağ paneli sıfırla
        if self._secili_kat_id == kid:
            self._secili_kat_id   = None
            self._secili_kat_isim = ""
            self.komp_listesini_yenile()

        self.listeyi_yenile()
        # Envanter sekmesindeki ComboBox'ı güncelle
        self.envanter_sekmesi.kategorileri_guncelle()

        messagebox.showinfo(
            "✅ Başarılı",
            f"'{isim}' kategorisi silindi.\n"
            "Bağlı komponentlerin kategorisi 'Atanmamış' olarak güncellendi."
        )


# ─────────────────────────────────────────────────────────────────
# Ana Uygulama Penceresi
# ─────────────────────────────────────────────────────────────────
class EnvanterUygulamasi(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("⚡ Elektronik Komponent Envanteri")
        self.geometry("1280x760")
        self.minsize(960, 600)
        self.configure(fg_color=RENK["bg_ana"])

        # Simge (varsa)
        try:
            self.iconbitmap("icon.ico")
        except Exception:
            pass

        # Veritabanı
        self.db = VeritabaniYonetici()

        self._arayuzu_olustur()

    def _arayuzu_olustur(self):
        # ── Sol kenar çubuğu ─────────────────────────────────────
        self.kenar = ctk.CTkFrame(self, fg_color=RENK["bg_kenar"],
                                   width=220, corner_radius=0)
        self.kenar.pack(side="left", fill="y")
        self.kenar.pack_propagate(False)

        # Logo / başlık
        logo = ctk.CTkFrame(self.kenar, fg_color=RENK["bg_kart"],
                             height=72, corner_radius=0)
        logo.pack(fill="x")
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="⚡",
                     font=("Segoe UI", 32)).pack(pady=(10, 0))
        ctk.CTkLabel(logo, text="Elektronik Envanter",
                     font=("Segoe UI", 11, "bold"),
                     text_color=RENK["vurgu"]).pack()

        ctk.CTkLabel(self.kenar, text="NAVİGASYON",
                     font=("Segoe UI", 9, "bold"),
                     text_color=RENK["metin_soluk"]).pack(pady=(16, 4), padx=16, anchor="w")

        # Navigasyon butonları
        self.nav_butonlar: dict[str, ctk.CTkButton] = {}
        nav_items = [
            ("envanter",    "🗃️  Envanter",       "Komponent stoğunu yönet"),
            ("kategoriler", "📁  Kategoriler",     "Kategorileri yönet ve filtrele"),
            ("projeler",    "🗂️  Projeler & BOM",  "Proje ve malzeme listesi"),
            ("istek",       "🛒  İstek Listesi",   "Alınacak komponentler"),
        ]
        for anahtar, metin, ipucu in nav_items:
            btn = ctk.CTkButton(
                self.kenar, text=metin,
                anchor="w",
                height=42,
                corner_radius=8,
                font=("Segoe UI", 12),
                fg_color="transparent",
                hover_color=RENK["bg_kart"],
                text_color=RENK["metin"],
                command=lambda a=anahtar: self.sekmeye_git(a)
            )
            btn.pack(fill="x", padx=8, pady=2)
            self.nav_butonlar[anahtar] = btn

        # Alt bilgi
        alt = ctk.CTkFrame(self.kenar, fg_color="transparent")
        alt.pack(side="bottom", fill="x", pady=8)
        ctk.CTkLabel(alt,
                     text=f"v1.0  |  SQLite  |  {datetime.now().strftime('%Y')}",
                     font=("Segoe UI", 9),
                     text_color=RENK["metin_soluk"]).pack()

        # ── İçerik alanı ─────────────────────────────────────────
        self.icerik = ctk.CTkFrame(self, fg_color=RENK["bg_ana"], corner_radius=0)
        self.icerik.pack(side="right", fill="both", expand=True)

        # Sekme widget'ları oluştur
        # Not: KategoriYonetimSekmesi, envanter sekmesine referans alır;
        #       bu yüzden önce EnvanterSekmesi oluşturulur.
        envanter_sekmesi = EnvanterSekmesi(self.icerik, self.db)
        self.sekmeler: dict[str, ctk.CTkFrame] = {
            "envanter":    envanter_sekmesi,
            "kategoriler": KategoriYonetimSekmesi(self.icerik, self.db,
                                                  envanter_sekmesi),
            "projeler":    ProjelerSekmesi(self.icerik, self.db),
            "istek":       IstekListesiSekmesi(self.icerik, self.db),
        }

        # Varsayılan sekme
        self.aktif_sekme: str | None = None
        self.sekmeye_git("envanter")

        # Kapanış olayı
        self.protocol("WM_DELETE_WINDOW", self._kapat)

    def sekmeye_git(self, anahtar: str):
        if self.aktif_sekme == anahtar:
            return

        # Önceki sekmeyi gizle
        if self.aktif_sekme and self.aktif_sekme in self.sekmeler:
            self.sekmeler[self.aktif_sekme].pack_forget()

        # Aktif olmayan butonları sıfırla
        for k, btn in self.nav_butonlar.items():
            btn.configure(fg_color=RENK["bg_kart"] if k == anahtar else "transparent",
                          text_color=RENK["vurgu"] if k == anahtar else RENK["metin"])

        # Yeni sekmeyi göster
        self.aktif_sekme = anahtar
        sekme = self.sekmeler[anahtar]
        sekme.pack(fill="both", expand=True)

        # Proje sekmesine geçildiğinde BOM komponent listesini güncelle
        if anahtar == "projeler":
            self.sekmeler["projeler"].bom_komponentleri_guncelle()

        # Kategori sekmesine geçildiğinde listeyi taze verilerle yenile
        if anahtar == "kategoriler":
            kat_sekmesi = self.sekmeler["kategoriler"]
            kat_sekmesi.listeyi_yenile()
            kat_sekmesi.komp_listesini_yenile()

    def _kapat(self):
        self.db.kapat()
        self.destroy()


# ─────────────────────────────────────────────────────────────────
# Giriş Noktası
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uygulama = EnvanterUygulamasi()
    uygulama.mainloop()
