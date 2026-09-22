import os
from cardd_data_loader import build_cardd_dataset
from cardd_db import import_dataset_to_postgres

def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    dataset = build_cardd_dataset("./rawdata")

    print("Etiquetas:", len(dataset["etiquetas"]))
    print("Imágenes:", len(dataset["imagenes"]))
    print("Instancias:", len(dataset["instancias"]))

    import_dataset_to_postgres(dataset, database_url)
    print("Importación completada correctamente.")

if __name__ == "__main__":
    main()