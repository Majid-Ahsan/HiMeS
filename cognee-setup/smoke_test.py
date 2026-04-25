# Cognee Smoke Test
# Validiert dass die Installation funktioniert
# Nutzt minimale Test-Daten und prüft Knowledge-Graph-Aufbau und Query
# WICHTIG: Dieses Skript ist NUR für Server-Test gedacht, NICHT für Mac

import asyncio
import cognee


async def smoke_test():
    print("Cognee Smoke Test gestartet")

    test_text = """
    Majid Ahsan ist Kardiologe in Mülheim an der Ruhr.
    Er hat zwei Söhne: Taha und Hossein.
    Sein Onkel Reza Ahmadi wohnt in Teheran und ist auch Arzt.
    Reza nimmt Metformin wegen Diabetes Typ 2 seit 2019.
    """

    print("Füge Test-Daten hinzu...")
    await cognee.add(test_text)

    print("Cognify-Pipeline ausführen (Knowledge Graph aufbauen)...")
    print("Dies kann 30-60 Sekunden dauern beim ersten Mal")
    await cognee.cognify()

    print("Frage 'Wer ist Reza?' an...")
    results = await cognee.search("Wer ist Reza?")

    print("\n=== Ergebnisse ===")
    for r in results:
        print(r)

    print("\nSmoke Test abgeschlossen")
    print("Erwartet: Antwort enthält Onkel-Beziehung, Teheran, Arzt, Metformin")


if __name__ == "__main__":
    asyncio.run(smoke_test())
