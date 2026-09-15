from app.db.session import SessionLocal, init_db
from app.models.schema import Camera

def seed():
    init_db()
    db = SessionLocal()
    cam = db.query(Camera).filter(Camera.name == "BOP-03 North Perimeter (CCTV)").first()
    if not cam:
        new_cam = Camera(
            name="BOP-03 North Perimeter (CCTV)",
            source_type="VIDEO_FILE",
            source_uri="./data/demo/sample_cctv.mp4",
            enabled=True,
            status="CONNECTED"
        )
        db.add(new_cam)
        db.commit()
        db.refresh(new_cam)
        print(f"Seeded primary CCTV demo camera: BOP-03 North Perimeter (CCTV) (ID: {new_cam.id})")
    else:
        cam.source_uri = "./data/demo/sample_cctv.mp4"
        cam.enabled = True
        db.commit()
        print(f"Updated CCTV camera with ID: {cam.id}")
    db.close()

if __name__ == "__main__":
    seed()
