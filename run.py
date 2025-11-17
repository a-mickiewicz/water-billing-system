"""
Prosty skrypt uruchamiający aplikację Water Billing System.
"""

import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("Water Billing System")
    print("=" * 50)
    print("\nAplikacja dostępna pod adresem: http://localhost:8000")
    print("Dokumentacja API: http://localhost:8000/docs")
    print("\nNaciśnij Ctrl+C aby zatrzymać serwer\n")
    print("-" * 50)
    
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

