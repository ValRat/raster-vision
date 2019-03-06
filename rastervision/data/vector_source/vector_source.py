from abc import ABC, abstractmethod

import shapely

from rastervision.data.vector_source.class_inference import (
    ClassInference, ClassInferenceOptions)


def transform_geojson(geojson,
                      line_bufs=None,
                      point_bufs=None,
                      crs_transformer=None):
    new_features = []
    for f in geojson['features']:
        # This was added to handle empty geoms which appear when using
        # OSM vector tiles.
        if f['geometry'].get('coordinates') is None:
            continue

        geom = shapely.geometry.shape(f['geometry'])
        geoms = [geom]

        # Convert MultiX to list of X.
        if geom.geom_type in ['MultiPolygon', 'MultiPoint', 'MultiLineString']:
            geoms = list(geom)

        # Buffer points and linestrings.
        class_id = f['properties']['class_id']
        new_geoms = []
        for g in geoms:
            if g.geom_type == 'LineString':
                line_buf = 1
                if line_bufs is not None:
                    line_buf = line_bufs.get(class_id, 1)
                new_geoms.append(g.buffer(line_buf))
            elif g.geom_type == 'Point':
                point_buf = 1
                if point_bufs is not None:
                    point_buf = point_bufs.get(class_id, 1)
                new_geoms.append(g.buffer(point_buf))
            else:
                # Use buffer trick to handle self-intersecting polygons.
                # Note: buffer returns a MultiPolygon if there is a bowtie.
                new_geoms.extend(list(g.buffer(0)))
        geoms = new_geoms

        if crs_transformer is not None:
            # Convert map to pixel coords.
            def transform_shape(x, y, z=None):
                return crs_transformer.map_to_pixel((x, y))

            geoms = [shapely.ops.transform(transform_shape, g) for g in geoms]

        for g in geoms:
            new_f = {
                'type': 'Feature',
                'geometry': shapely.mapping(g),
                'properties': f['properties']
            }
            new_features.append(new_f)

    return {'type': 'FeatureCollection', 'features': new_features}


class VectorSource(ABC):
    """A source of vector data.

    Uses GeoJSON as its internal representation of vector data.
    """

    def __init__(self,
                 crs_transformer,
                 line_bufs=None,
                 point_bufs=None,
                 class_inf_opts=None):
        """Constructor.

        Args:
            class_inf_opts: (ClassInferenceOptions)
        """
        self.crs_transformer = crs_transformer
        self.line_bufs = line_bufs
        self.point_bufs = point_bufs
        if class_inf_opts is None:
            class_inf_opts = ClassInferenceOptions()
        self.class_inference = ClassInference(class_inf_opts)

        self.geojson = None

    def get_geojson(self, to_pixel=True):
        if self.geojson is None:
            self.geojson = self._get_geojson()
        return transform_geojson(
            self.geojson,
            self.line_bufs,
            self.point_bufs,
            crs_transformer=(self.crs_transformer if to_pixel else None))

    @abstractmethod
    def _get_geojson(self):
        pass
