from taskgraph.transforms.base import TransformSequence

from ..build_config import get_path, get_upstream_deps_for_all_gradle_projects


transforms = TransformSequence()


@transforms.add
def add_components_optimization(config, tasks):
    for task in tasks:
        attributes = task.get("attributes", {})
        # TODO bug 1806454 - Use a single attribute instead of 2. This is a historical
        # discrepancy where A-C are labeled by build-types but APKs by release ones.
        #
        # The monorepo migration made this discrepancy more obvious compared to when
        # A-C and APKs lived in different repos
        build_type = attributes.get("build-type", "")
        release_type = attributes.get("release-type", "")

        # We want to optimize away tasks on all android-components and APKs as long as
        # these tasks are not labeled nightly, beta, or release.
        #
        # Any change that impacts all a-c (e.g. a change in the a-c gradle config)
        # should also trigger APK builds and tests.
        if all(type_ not in ("nightly", "beta", "release") for type_ in (build_type, release_type)):
            optimization = task.setdefault("optimization", {})
            skip_unless_changed = optimization.setdefault("skip-unless-changed", [])
            skip_unless_changed.extend([
                "android-components/build.gradle",
                "android-components/settings.gradle",
                "android-components/buildSrc.*",
                "android-components/gradle.properties",
                "android-components/gradle/wrapper/gradle-wrapper.properties",
                "android-components/plugins/dependencies/**",
            ])

        yield task


@transforms.add
def extend_optimization_if_one_already_exists(config, tasks):
    deps_per_component = get_upstream_deps_for_all_gradle_projects()

    for task in tasks:
        optimization = task.get("optimization")
        if optimization:
            skip_unless_changed = optimization["skip-unless-changed"]

            component = task["attributes"].get("component")
            if not component:
                component = "app" # == Focus. TODO: Support Fenix
            # TODO Remove this special case when ui-test.sh is able to accept "browser-engine-gecko"
            if component == "browser":
                component = "browser-engine-gecko"

            dependencies = deps_per_component[component]
            component_and_deps = [component] + dependencies

            skip_unless_changed.extend(sorted([
                _get_path(component)
                for component in component_and_deps
            ]))

        yield task


def _get_path(component):
    if component == "app":
        return "focus-android/**"
    elif component == "service-telemetry":
        return "focus-android/service-telemetry/**"
    else:
        return f"android-components/{get_path(component)}/**"
