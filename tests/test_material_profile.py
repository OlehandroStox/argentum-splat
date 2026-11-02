"""Numeric shader/profile and legacy migration tests, without emulating Redshift.

Expected sample values are from the deployed SuperSplat PlayCanvas
2.23.3/b7655d8 forward shader. Native OSL compilation/rendering is a separate
host check; these tests evaluate the scalar expressions in the embedded source.
"""
import ast
from contextlib import nullcontext
import math
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from test_native_actions import ROOT, function
from argentum_splat.geometry import gaussian_support


def shader_constants():
    tree = ast.parse((ROOT/'argentum_splat/materials.py').read_text(encoding='utf8'))
    names = ('LEGACY_GAUSSIAN_SOURCE', 'LEGACY_CAPPED_GAUSSIAN_SOURCE',
             'LEGACY_NORMALIZED_GAUSSIAN_SOURCE', 'GAUSSIAN_SOURCE')
    return {node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names}


def evaluate_shader(source, opacity, x, y, profile=0):
    """Evaluate this shader's scalar OSL assignments, not a duplicate formula."""
    context = dict(u=(x+1)/2, v=(y+1)/2, SplatOpacity=opacity,
                   GaussianProfile=profile, exp=math.exp, min=min, max=max, color=float,
                   clamp=lambda value, low, high: min(high, max(low, value)))
    body = source.split('{', 1)[1].rsplit('}', 1)[0]
    for statement in body.split(';'):
        statement = statement.strip()
        if not statement:
            continue
        match = re.fullmatch(r'(?:float\s+)?(\w+)\s*=\s*(.*)', statement, re.S)
        if not match:
            raise AssertionError('Unsupported scalar OSL statement: '+statement)
        name, expression = match.groups()
        ternary = re.fullmatch(r'color\((.*?)\?(.*?)\:(.*?)\)', expression, re.S)
        if ternary:
            condition, yes, no = ternary.groups()
            expression = '('+yes+') if ('+condition+') else ('+no+')'
        elif '?' in expression:
            condition, branches = expression.split('?', 1)
            yes, no = branches.split(':', 1)
            expression = '('+yes+') if ('+condition+') else ('+no+')'
        context[name] = eval(expression, {'__builtins__': {}}, context)
    return context['GaussianOpacity']


class SuperSplatMaterialProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.constants = shader_constants()
        cls.source = cls.constants['GAUSSIAN_SOURCE']

    def test_deployed_reference_samples_and_full_opacity_center(self):
        # The old pure Gaussian (.606531, .135335, .043937 at 1/2/2.5 sigma)
        # cannot satisfy these samples; the former .99 center cap also fails.
        for sigma, expected in ((0., 1.), (1., .5991895604387956),
                                (2., .11920292202211757),
                                (2.5, .02609932046352451)):
            with self.subTest(sigma=sigma):
                self.assertAlmostEqual(evaluate_shader(self.source, 1., sigma/3., 0.),
                                       expected, places=13)
                self.assertAlmostEqual(evaluate_shader(self.source, .5, 0., sigma/3.),
                                       .5*expected, places=13)

    def test_radial_cutoff_has_no_square_corner_or_three_sigma_halo(self):
        for x, y in ((math.sqrt(8)/3, 0.), (0., 1.), (1., 1.),
                     (.7, .7), (-.7, .7), (0., -1.)):
            self.assertEqual(evaluate_shader(self.source, 1., x, y), 0.)
        diagonal = 2./(3.*math.sqrt(2.))
        self.assertAlmostEqual(evaluate_shader(self.source, 1., diagonal, diagonal),
                               .11920292202211757, places=13)

    def test_cutoff_and_source_opacity_clamping(self):
        self.assertEqual(evaluate_shader(self.source, -1., 0., 0.), 0.)
        self.assertEqual(evaluate_shader(self.source, 2., 0., 0.), 1.)
        self.assertEqual(evaluate_shader(self.source, 1/255-1e-12, 0., 0.), 0.)
        self.assertAlmostEqual(evaluate_shader(self.source, 1/255, 0., 0.), 1/255)
        self.assertEqual(evaluate_shader(self.source, .01, 2/3, 0.), 0.)
        self.assertGreater(evaluate_shader(self.source, .01, 1/3, 0.), 1/255)

    def test_photos_profile_uses_classic_gaussian(self):
        for sigma in (0., 1., 2., 2.5):
            self.assertAlmostEqual(evaluate_shader(self.source, 1., sigma/3., 0., 1),
                                   min(.999, math.exp(-.5*sigma*sigma)), places=13)

    def test_geometry_support_never_crops_a_visible_reference_sample(self):
        for opacity in (.004, .01, .03, .1, .5, 1.):
            support = gaussian_support(opacity)
            for radius in (support+1e-5, min(1., support+.01), 1.):
                if radius > support:
                    self.assertEqual(evaluate_shader(self.source, opacity, radius, 0.), 0.)

    def test_kernel_name_is_distinct_from_both_legacy_programs(self):
        kernel = re.match(r'shader (\w+)\(', self.source)[1]
        for name in ('LEGACY_GAUSSIAN_SOURCE', 'LEGACY_CAPPED_GAUSSIAN_SOURCE', 'LEGACY_NORMALIZED_GAUSSIAN_SOURCE'):
            self.assertNotEqual(kernel, re.match(r'shader (\w+)\(', self.constants[name])[1])

    def migration(self, initial):
        state = {'source': initial}
        port = SimpleNamespace(GetPortValue=lambda: state['source'],
                               SetPortValue=Mock(side_effect=lambda value: state.update(source=value)))
        node = object()
        transaction = SimpleNamespace(Commit=Mock())
        begin = Mock(return_value=nullcontext(transaction))
        read_input = Mock(return_value=port)
        read_output = Mock()
        context = dict(self.constants, OSL='osl.', _node=lambda graph, name: node,
                       _input=read_input, _output=read_output, _begin_transaction=begin)
        upgrade = function('materials.py', '_upgrade_gaussian_node', context)
        return upgrade, state, port, transaction, begin, read_input, read_output

    def test_both_known_legacy_shaders_migrate_once_with_caller_undo(self):
        for name in ('LEGACY_GAUSSIAN_SOURCE', 'LEGACY_CAPPED_GAUSSIAN_SOURCE', 'LEGACY_NORMALIZED_GAUSSIAN_SOURCE'):
            with self.subTest(profile=name):
                upgrade, state, port, transaction, begin, inputs, outputs = self.migration(
                    '\n'+self.constants[name]+'\n')
                graph, undo = object(), object()
                self.assertTrue(upgrade(graph, undo))
                self.assertEqual(state['source'], self.source)
                begin.assert_called_once_with(graph, undo)
                transaction.Commit.assert_called_once_with()
                self.assertEqual(inputs.call_args.args[1], 'osl.splatopacity')
                self.assertEqual(outputs.call_args.args[1], 'osl.gaussianopacity')
                self.assertFalse(upgrade(graph, undo))
                port.SetPortValue.assert_called_once_with(self.source)

    def test_custom_programs_and_current_profile_are_not_replaced(self):
        for original in (self.source, self.constants['LEGACY_GAUSSIAN_SOURCE']+'// edited',
                         self.constants['LEGACY_CAPPED_GAUSSIAN_SOURCE'].replace('0.99', '0.95'),
                         'shader MyGaussian() {}'):
            upgrade, state, port, transaction, begin, inputs, outputs = self.migration(original)
            self.assertFalse(upgrade(object()))
            self.assertEqual(state['source'], original)
            port.SetPortValue.assert_not_called()
            begin.assert_not_called()
            outputs.assert_not_called()


if __name__ == '__main__':
    unittest.main()
