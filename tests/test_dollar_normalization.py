import pytest
from backend.normalizer import clean_unwanted_dollars, clean_html_and_math

def test_bare_number_dollars_cleaned():
    # User's exact reported cases
    assert clean_unwanted_dollars("Số bé nhất có $2$ chữ số") == "Số bé nhất có 2 chữ số"
    assert clean_unwanted_dollars("Số $ 28$ có chữ số hàng đơn vị") == "Số 28 có chữ số hàng đơn vị"
    assert clean_unwanted_dollars("số tròn chục liền sau của $ 32.$ Số đó là") == "số tròn chục liền sau của 32. Số đó là"
    assert clean_unwanted_dollars("Chữ số hàng chục của $ 40$ là:") == "Chữ số hàng chục của 40 là:"
    assert clean_unwanted_dollars("lúc $7$ giờ $15$ phút và đến tỉnh B lúc $9$ giờ $45$ phút") == "lúc 7 giờ 15 phút và đến tỉnh B lúc 9 giờ 45 phút"
    assert clean_unwanted_dollars("Một can đựng $15l$ dầu, người ta rót ra $7l$ dầu.") == "Một can đựng 15l dầu, người ta rót ra 7l dầu."
    assert clean_unwanted_dollars("trong thời gian $3 giờ$.") == "trong thời gian 3 giờ."

def test_currency_dollars_strictly_preserved():
    # Real USD currency notation must NOT be destroyed
    text = "Emily saves $6 on Monday, $8 on Tuesday. How many dollars? [WKC] Emily tiết kiệm được $6 vào thứ Hai, $8 vào thứ Ba."
    assert clean_unwanted_dollars(text) == text

def test_genuine_latex_formulas_preserved():
    # Fractions, exponents, subscripts, math symbols, formatted units
    assert clean_unwanted_dollars("Tính giá trị của: $A = \\frac{1}{2} + \\frac{1}{6}$") == "Tính giá trị của: $A = \\frac{1}{2} + \\frac{1}{6}$"
    assert clean_unwanted_dollars("Tìm hai chữ số tận cùng của $7^{2024}$.") == "Tìm hai chữ số tận cùng của $7^{2024}$."
    assert clean_unwanted_dollars("vận tốc $48\\text{ km/h}$.") == "vận tốc $48\\text{ km/h}$."
    assert clean_unwanted_dollars("Hai thành phố $A$ và $B$ cách nhau") == "Hai thành phố $A$ và $B$ cách nhau"
    assert clean_unwanted_dollars("Tìm số tự nhiên $x$, biết: $x - 38 = 45$") == "Tìm số tự nhiên $x$, biết: $x - 38 = 45$"

def test_clean_html_and_math_integration():
    html = "<p>Số bé nhất có <span class=\"math-tex\">\\( 2 \\)</span> chữ số</p>"
    clean_html, clean_text = clean_html_and_math(html)
    assert clean_text == "Số bé nhất có 2 chữ số"
    assert "$2$" not in clean_html
    assert "$2$" not in clean_text
