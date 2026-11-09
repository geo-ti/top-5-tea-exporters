# LinkedIn draft: Day 13 (Interactions) - V1, static gravity map

---

**Day 13 of #30DayMapChallenge: Interactions. Which tea routes defy distance?**

Yesterday (Day 12, Power) I mapped how much energy goes into growing and drying the world's coffee and tea: about 84 TWh a year. That tea then has to travel. Today's theme is Interactions, so I followed the tea from the five biggest exporters (Kenya, China, Sri Lanka, India and Vietnam) to their top 15 buyers each.

Raw trade volumes mostly show who is big. To find the interesting corridors, I used the gravity model from spatial interaction theory. Trade between two places should grow with their "mass" and shrink with distance:

Expected(i,j) = (tea production of i) x (GDP of j) / (distance i,j)^1.2

Then I compared what each corridor actually ships (UN Comtrade, HS 0902) with what gravity predicts. Purple arcs trade far more than production, GDP and distance alone would suggest. Grey arcs trade less.

What stands out:
- **Kenya -> Pakistan:** 221,000 tonnes across 4,770 km. It is the largest single tea corridor on the map, and about 60 times the typical gravity ratio. Pakistan's daily chai runs on Mombasa auction tea.
- **Sri Lanka -> Iraq:** about 34,000 tonnes, around 20 times the typical ratio. Ceylon tea is a fixture of Iraqi tea culture. Russia is also above expectation, though less dramatically (about 2.6x).
- **China -> Morocco:** 81,000 tonnes of green gunpowder tea across 9,600 km, about 20 times the typical ratio. The same green tea trail carries on to Mauritania, Senegal, The Gambia and Ghana, all strongly positive.
- **The opposite case:** China -> USA, China -> Japan and India -> China trade far less tea than their huge economies and short distances (for Japan and China) would predict. Those markets have their own tea or other habits.

Gravity explains a lot of trade, but not culture. The biggest anomalies are where a drinking ritual, a historic trade tie or a taste for one kind of tea beats the pull of the nearest rich market.

Built with Python (pandas, GeoPandas, the UN Comtrade and World Bank APIs) and QGIS, in plain lat/long.

Caveats: this is a simple gravity model with a fixed distance exponent of 1.2 and no other variables. Production is FAOSTAT fresh leaf, and trade is net weight as reported by the exporter (Vietnam 2023, others 2024).

Data: UN Comtrade, World Bank Open Data, UN FAOSTAT, Natural Earth.

#30DayMapChallenge #GIS #DataVisualization #Cartography #QGIS #Python #Tea #Trade #SpatialInteraction
