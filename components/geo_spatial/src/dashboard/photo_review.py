
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="TravelMind Photo Review",
    page_icon="🖼️",
    layout="wide"
)

ROOT = Path(__file__).resolve().parents[2]

CSV_FILE = (
    ROOT / "config"
    / "attraction_image_candidates.csv"
)

IMAGE_DIR = (
    ROOT / "assets" / "images" / "attractions"
)

st.title("🖼️ TravelMind – Photo Review")
st.caption(
    "Review attraction photographs before "
    "using them in the tourist dashboard."
)

if not CSV_FILE.exists():
    st.error("Image metadata CSV not found.")
    st.stop()

df = pd.read_csv(
    CSV_FILE,
    encoding="utf-8-sig"
).fillna("")

if "review_status" not in df.columns:
    df["review_status"] = "needs_visual_review"

total = len(df)
approved = (df["review_status"] == "approved").sum()
rejected = (df["review_status"] == "rejected").sum()
pending = total - approved - rejected

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total photos", total)
c2.metric("Approved", int(approved))
c3.metric("Rejected", int(rejected))
c4.metric("Pending", int(pending))

status_filter = st.selectbox(
    "Filter photographs",
    [
        "All",
        "needs_visual_review",
        "approved",
        "rejected"
    ]
)

if status_filter == "All":
    filtered = df
else:
    filtered = df[
        df["review_status"] == status_filter
    ]

if filtered.empty:
    st.info("No photographs match this filter.")

for index in filtered.index:

    row = df.loc[index]

    name = str(row["attraction_name"])
    filename = str(row["image_file"])

    image_path = IMAGE_DIR / filename

    with st.container(border=True):

        left, right = st.columns([1, 2])

        with left:
            if image_path.is_file():
                st.image(
                    str(image_path),
                    width="stretch"
                )
            else:
                st.warning("Image file missing.")

        with right:
            st.subheader(name)

            st.write(
                "**Wikimedia file:**",
                row.get("wikimedia_file_title", "")
            )

            st.write(
                "**Creator:**",
                row.get("creator", "")
            )

            st.write(
                "**License:**",
                row.get("license", "")
            )

            source_url = str(
                row.get("source_page", "")
            )

            if source_url.startswith("https://"):
                st.link_button(
                    "View original Wikimedia image",
                    source_url
                )

            st.write(
                "**Current status:**",
                row["review_status"]
            )

            decision = st.radio(
                "Review decision",
                [
                    "needs_visual_review",
                    "approved",
                    "rejected"
                ],
                index=(
                    [
                        "needs_visual_review",
                        "approved",
                        "rejected"
                    ].index(row["review_status"])
                    if row["review_status"] in [
                        "needs_visual_review",
                        "approved",
                        "rejected"
                    ]
                    else 0
                ),
                key=f"decision_{index}"
            )

            if st.button(
                "Save decision",
                key=f"save_{index}"
            ):

                df.loc[
                    index,
                    "review_status"
                ] = decision

                df.to_csv(
                    CSV_FILE,
                    index=False,
                    encoding="utf-8-sig"
                )

                st.success(
                    f"Saved review for {name}"
                )

                st.rerun()

st.divider()

st.info(
    "Approve only if the photo correctly depicts "
    "the named attraction and you have checked "
    "the image's license and attribution requirements. "
    "This review does not verify the attraction "
    "record itself."
)
