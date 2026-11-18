/**
 * On-demand world geography.
 *
 * The full list is ~2.1 MB because it carries 148k areas; it lives in the API
 * project and never ships with the browser app. The index (`/catalogue/geography.json`,
 * ~80 KB) holds country -> states, which is everything a country or state picker
 * needs; a country's area tree is a separate file (usually a few KB) fetched the
 * first time an area list is used.
 *
 *   const geo = await GeographySource.load(url);   // {tree, files}
 *   geo.tree["Nigeria"]["Abia"]                    // [] until areas arrive
 *   await GeographySource.areas(url, "Nigeria");   // fills every state's areas
 *
 * A plain `{country: {state: [areas]}}` payload (the old single file) is still
 * understood, so a stale URL keeps working.
 */
(function (root) {
  const trees = new Map();
  const loadedCountries = new Set();

  const expand = (index) => {
    const tree = {};
    Object.entries((index && index.countries) || {}).forEach(([country, states]) => {
      tree[country] = {};
      (states || []).forEach((state) => {
        tree[country][state] = [];
      });
    });
    return tree;
  };

  const load = (url) => {
    if (!url) return Promise.reject(new Error('geography url missing'));
    if (trees.has(url)) return Promise.resolve(trees.get(url));
    return fetch(url, { credentials: 'same-origin' })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!data || typeof data !== 'object') throw new Error('geography unavailable');
        const value = data.countries
          ? { tree: expand(data), files: data.files || {} }
          : { tree: data, files: {} };
        trees.set(url, value);
        return value;
      });
  };

  const areas = (url, country) =>
    load(url).then((geo) => {
      const key = `${url}|${country}`;
      if (!country || !geo.tree[country] || loadedCountries.has(key)) {
        return geo.tree[country] || {};
      }
      const file = geo.files[country];
      if (!file) {
        loadedCountries.add(key);
        return geo.tree[country];
      }
      const href = file.indexOf('://') > -1 || file.charAt(0) === '/' ? file : `/static/${file}`;
      return fetch(href, { credentials: 'same-origin' })
        .then((response) => (response.ok ? response.json() : null))
        .then((value) => {
          if (value && typeof value === 'object') {
            Object.entries(value).forEach(([state, list]) => {
              if (Array.isArray(list)) geo.tree[country][state] = list;
            });
          }
          loadedCountries.add(key);
          return geo.tree[country];
        })
        .catch(() => {
          loadedCountries.add(key);
          return geo.tree[country];
        });
    });

  root.GeographySource = { load, areas };
})(window);
