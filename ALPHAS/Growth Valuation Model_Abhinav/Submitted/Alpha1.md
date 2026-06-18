quantile(
 add(
  group_rank(star_val_sector_rank,sector),
  group_rank(ts_delta(star_val_sector_rank,10),sector)
 ),
 driver="gaussian",
 sigma=1.5
)

![alt text](image.png)

GLDB D1