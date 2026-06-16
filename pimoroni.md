# Automation HAT Mini jako interfejs czujnika indukcyjnego

## Cel zastosowania

W projekcie Windows_CCounter nakładka **Pimoroni Automation HAT Mini** może pełnić rolę
bezpieczniejszego i wygodniejszego interfejsu pomiędzy Raspberry Pi a czujnikiem
indukcyjnym **E2S-H4N1 4 mm 5V**. Zamiast podawać sygnał bezpośrednio na GPIO Raspberry Pi,
sygnał detekcji można wprowadzić na wejście **IN1** nakładki, a następnie odczytywać go z
poziomu aplikacji Python.

Takie podejście upraszcza okablowanie, daje gotowe zaciski śrubowe i separuje logikę projektu
od surowej obsługi pinów GPIO.

## Dlaczego Automation HAT Mini

Najważniejsze zalety tej nakładki w naszym zastosowaniu:

- wejścia cyfrowe przystosowane do sygnałów automatyki niskonapięciowej,
- wygodne zaciski śrubowe do podłączenia przewodów czujnika,
- gotowa biblioteka Python `automationhat`,
- możliwość dalszej rozbudowy o dodatkowe wejścia, wyjścia i pomiary analogowe,
- mniejsze ryzyko uszkodzenia GPIO Raspberry Pi przy błędnym podłączeniu sygnału.

Z dokumentacji producenta wynika, że rodzina Automation HAT / HAT Mini nadaje się do pracy
z sygnałami do **24V**, ale **nie wolno** jej używać do napięć sieciowych ani sygnałów powyżej
24V.

## Użycie wejścia IN1 z czujnikiem E2S-H4N1 4 mm 5V

Planowane połączenie:

- czujnik indukcyjny **E2S-H4N1 4 mm 5V** dostarcza sygnał detekcji,
- sygnał wyjściowy czujnika trafia na **IN1** nakładki,
- Raspberry Pi odczytuje stan wejścia przez bibliotekę `automationhat`,
- aplikacja traktuje zmianę stanu wejścia jako zdarzenie z czujnika.

Schemat logiczny połączenia:

```text
E2S-H4N1 5V  ->  Automation HAT Mini  ->  Raspberry Pi  ->  Windows_CCounter
	OUT       ->         IN1
	GND       ->         GND
	+5V       ->   zasilanie czujnika
```

## Uwagi elektryczne

Przed podłączeniem należy potwierdzić w karcie katalogowej czujnika:

- typ wyjścia czujnika,
- poziomy napięć na wyjściu,
- wspólną masę układu,
- maksymalny prąd i sposób polaryzacji wyjścia.

Dla tego projektu przyjmujemy użycie wersji **5V** i wykorzystanie wyjścia czujnika wyłącznie
jako sygnału binarnego obecności obiektu. Jeżeli konkretna odmiana E2S-H4N1 ma wyjście typu
NPN / open collector lub inną charakterystykę niż klasyczne wyjście logiczne, połączenie należy
zweryfikować pomiarem i kartą katalogową przed uruchomieniem produkcyjnym.

Najważniejsze zasady:

- nie podawać napięcia sieciowego na nakładkę,
- nie przekraczać parametrów wejściowych nakładki,
- prowadzić wspólną masę czujnika i nakładki,
- sprawdzić stan spoczynkowy sygnału, aby poprawnie odwzorować logikę aktywnego wejścia w aplikacji.

## Korzyści względem bezpośredniego GPIO

Wpięcie czujnika do **IN1** zamiast bezpośrednio do GPIO Raspberry Pi jest zalecane szczególnie,
gdy:

- czujnik pracuje w środowisku przemysłowym i przewody są dłuższe,
- chcemy ograniczyć ryzyko błędu przy uruchomieniu i serwisie,
- planowana jest dalsza rozbudowa układu o kolejne sygnały,
- zależy nam na czytelniejszym okablowaniu w szafie lub obudowie.

Bezpośrednie GPIO nadal może być użyte w wariancie uproszczonym, ale wymaga większej ostrożności
przy dopasowaniu poziomów napięć i sposobu podłączenia czujnika.

## Integracja programowa

Docelowo aplikacja może obsługiwać dwa warianty wejścia sygnału:

- **GPIO bezpośrednie** – obecny, prostszy wariant sprzętowy,
- **Automation HAT Mini / IN1** – wariant zalecany dla instalacji na Raspberry Pi.

Wariant z Automation HAT Mini wymaga użycia biblioteki producenta oraz odczytu stanu wejścia
`input.one` jako źródła sygnału pomiarowego.

Na obecnym etapie repozytorium bazowa ścieżka sprzętowa aplikacji nadal korzysta z bezpośredniego
GPIO Raspberry Pi. Ten dokument opisuje docelowy wariant integracji, w którym źródłem sygnału
pomiarowego staje się wejście **IN1** nakładki Automation HAT Mini.

Przykład odczytu:

```python
import automationhat

sensor_active = automationhat.input.one.read()
```

## Źródło

Dokumentacja producenta:

https://learn.pimoroni.com/article/getting-started-with-automation-hat-and-phat

