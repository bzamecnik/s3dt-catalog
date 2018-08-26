- zobrazit nové produkty - kód a názvy produktů
- [x] umožnit, aby šlo v Shoptetu nastavit vlastní cenu a nepřepisovat ji z ED
- upozornit na změnu nákupní ceny
- umožnit ze vstupů (ED a shoptet) vygenerovat nejen importní XML, ale i přehled změn

- [x] hodilo by se ukládat sklad do databáze
	- buď aktuální stav, nebo celou historii
- ~https://addons.heroku.com/mongolab~
	- Sandbox - free, 496 MB storage

- při stahování vstupů by byl pěkný progress bar
- [x] stahování dělat jako background task
	- vložit job do fronty
	- zobrazovat informaci o progressu - job začal, procenta hotovo, job hotov
		- ideálně posílat server side events, jinak pollovat nebo manuální refresh
	- po skončení dát odkaz na výsledné XML ke stažení

- problémy:
	- [x] výpočet potřebujeme provést v background workeru mimo HTTP request
	- potřebujeme zřetězit několik jobů
		- stažení ED katalogu
		- stažení Shoptet katalogu
		- vygenerování Shoptet importu
	- [x] potřebujeme persistentně uložit výsledky každého jobu
	- chtěli bychom monitorovat progress jednotlivých jobů
	- [x] chtěli bychom stopnout běžící job
	- ukázat report o změnách v katalogu

- rozdělit konverzi ED XML:
	- parsovat vstupní XML z ED do iterátoru, který obsahuje pythoní struktury
	- generovat výstupní XML z pythoních struktur
- ukládat items z ED XML do monga
- ukládat items z Shoptet TSV do monga
- generovat Shoptet XML z mongo items
- zobrazovat změny v katalogu


- info:
	- v ED katalogu je cca ~66787~ > 180000 položek

- testování monga?
	- https://github.com/vmalloc/mongomock

- reagovat na situaci, kdy ED vrátit informaci, že XML katalog není k dispozici

- udělat mock serveru ED system a shoptetu

- zobrazovat produkty přes UI
- ukládat všechny unikátní verze produktů
	- pak z toho dělat porovnání
- importovat komplet celý katalog ze Shoptetu

---

- deploynout pres Docker
	- udelat mongo volume persistentni
	- pro produkci nemountovat zdrojaky, pro dev ano
