"""
EDA notebook-equivalent script.
Run: python ml/eda.py
Outputs: route network stats, busiest hubs, wind impact analysis.
"""
import os, psycopg2, pandas as pd, networkx as nx

DB = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/airline_opt")

def main():
    conn = psycopg2.connect(DB)
    routes_df = pd.read_sql("""
        SELECT r.origin, r.destination, r.distance_km, r.base_demand, r.base_fare_usd,
               a1.country AS o_country, a2.country AS d_country
        FROM routes r
        JOIN airports a1 ON a1.iata = r.origin
        JOIN airports a2 ON a2.iata = r.destination
        WHERE r.distance_km IS NOT NULL
    """, conn)

    print(f"Total routes: {len(routes_df)}")
    print(f"Avg distance: {routes_df.distance_km.mean():.0f} km")

    # Network graph
    G = nx.from_pandas_edgelist(routes_df, 'origin', 'destination')
    centrality = nx.degree_centrality(G)
    top_hubs = sorted(centrality.items(), key=lambda x: -x[1])[:10]
    print("\nTop 10 hubs by degree centrality:")
    for iata, c in top_hubs:
        print(f"  {iata}: {c:.4f}")

    # Transatlantic routes
    ta = routes_df[
        routes_df.apply(lambda r:
            r.o_country in ('US','CA') and r.d_country in ('GB','DE','FR','NL','ES','IE') or
            r.d_country in ('US','CA') and r.o_country in ('GB','DE','FR','NL','ES','IE'),
        axis=1)
    ]
    print(f"\nTransatlantic routes: {len(ta)}")
    print(f"  Avg distance: {ta.distance_km.mean():.0f} km")
    print(f"  Winter eastbound fuel saving (18%): ${ta.distance_km.mean() * 12 * 0.85 * 0.18:.0f} per flight")
    print(f"  Winter westbound fuel penalty (18%): ${ta.distance_km.mean() * 12 * 0.85 * 0.18:.0f} extra per flight")

    # Pakistan detour impact
    india_eu = routes_df[
        (routes_df.o_country == 'IN') & (routes_df.d_country.isin(['GB','DE','FR','NL']))
    ]
    print(f"\nIndia→Europe routes: {len(india_eu)}")
    detour_cost = 1200 * 12 * 0.85  # 1200km detour
    print(f"  Pakistan airspace detour cost: ${detour_cost:.0f} per flight")

    conn.close()

if __name__ == "__main__":
    main()
