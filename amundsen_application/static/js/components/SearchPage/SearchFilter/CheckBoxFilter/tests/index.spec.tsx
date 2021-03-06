import * as React from 'react';
import { shallow } from 'enzyme';

import { CheckBoxFilter, CheckBoxFilterProps, mapDispatchToProps, mapStateToProps } from '../';
import CheckBoxItem from 'components/common/Inputs/CheckBoxItem';

import globalState from 'fixtures/globalState';

import { GlobalState } from 'ducks/rootReducer';

import { FilterType, ResourceType } from 'interfaces';

describe('CheckBoxFilter', () => {
  const setup = (propOverrides?: Partial<CheckBoxFilterProps>) => {
    const props: CheckBoxFilterProps = {
      categoryId: 'database',
      checkboxProperties: [
        {
          label: 'BigQuery',
          value: 'bigquery'
        },
        {
          label: 'Hive',
          value: 'hive'
        }
      ],
      checkedValues: {
        'hive': true,
      },
      clearFilterByCategory: jest.fn(),
      updateFilterByCategory: jest.fn(),
      ...propOverrides
    };
    const wrapper = shallow<CheckBoxFilter>(<CheckBoxFilter {...props} />);
    return { props, wrapper };
  };

  describe('createCheckBoxItem', () => {
    const mockCategoryId = 'categoryId';
    let props;
    let wrapper;

    let checkBoxItem;
    let mockProperties;
    beforeAll(() => {
      const setupResult = setup();
      props = setupResult.props;
      wrapper = setupResult.wrapper;
      mockProperties = props.checkboxProperties[0];
      const content = wrapper.instance().createCheckBoxItem(mockCategoryId, 'testKey', mockProperties);
      checkBoxItem = shallow(<div>{content}</div>).find(CheckBoxItem);
    })

    it('returns a CheckBoxItem', () => {
      expect(checkBoxItem.exists()).toBe(true);
    });

    it('returns a CheckBoxItem with correct props', () => {
      const itemProps = checkBoxItem.props()
      expect(itemProps.checked).toBe(props.checkedValues[mockProperties.value]);
      expect(itemProps.name).toBe(mockCategoryId);
      expect(itemProps.value).toBe(mockProperties.value);
      expect(itemProps.onChange).toBe(wrapper.instance().onCheckboxChange)
    });

    it('returns a CheckBoxItem with correct labelText as child', () => {
      expect(checkBoxItem.children().text()).toBe(mockProperties.label)
    });
  });

  describe('onCheckboxChange', () => {
    const mockCategoryId = 'database';
    let props;
    let wrapper;
    let mockEvent;

    let clearCategorySpy;
    let updateCategorySpy;
    beforeAll(() => {
      const setupResult = setup();
      props = setupResult.props;
      wrapper = setupResult.wrapper;
      clearCategorySpy = jest.spyOn(props, 'clearFilterByCategory');
      updateCategorySpy = jest.spyOn(props, 'updateFilterByCategory');
    })

    it('calls props.clearFilterByCategory if no items will be checked', () => {
      clearCategorySpy.mockClear();
      mockEvent = { target: { name: mockCategoryId, value: 'hive', checked: false }};
      wrapper.instance().onCheckboxChange(mockEvent);
      expect(clearCategorySpy).toHaveBeenCalledWith(mockCategoryId)
    });

    it('calls props.updateFilterByCategory with expected parameters', () => {
      updateCategorySpy.mockClear();
      mockEvent = { target: { name: mockCategoryId, value: 'bigquery', checked: true}};
      const expectedCheckedValues = {
        ...props.checkedValues,
        'bigquery': true
      }
      wrapper.instance().onCheckboxChange(mockEvent);
      expect(updateCategorySpy).toHaveBeenCalledWith(mockCategoryId, expectedCheckedValues)
    });
  });

  describe('render', () => {
    let props;
    let wrapper;
    let createCheckBoxItemSpy;

    beforeAll(() => {
      const setupResult = setup();
      props = setupResult.props;
      wrapper = setupResult.wrapper;
      createCheckBoxItemSpy = jest.spyOn(wrapper.instance(), 'createCheckBoxItem');
      wrapper.instance().render();
    })
    it('calls createCheckBoxItem with correct parameters for each props.checkboxProperties', () => {
      props.checkboxProperties.forEach((item, index) => {
        expect(createCheckBoxItemSpy).toHaveBeenCalledWith(props.categoryId, `item:${props.categoryId}:${index}`,item)
      })
    })
  });

  describe('mapStateToProps', () => {
    const mockCategoryId = 'database';
    const props = setup({ categoryId: mockCategoryId }).props;
    const mockFilters = {
      'hive': true
    };

    const mockStateWithFilters: GlobalState = {
      ...globalState,
      search: {
        ...globalState.search,
        selectedTab: ResourceType.table,
        filters: {
          [ResourceType.table]: {
            [mockCategoryId]: mockFilters
          }
        }
      },
    };

    const mockStateWithOutFilters: GlobalState = {
      ...globalState,
      search: {
        ...globalState.search,
        selectedTab: ResourceType.user,
        filters: {
          [ResourceType.table]: {}
        }
      },
    };

    let result;
    beforeEach(() => {
      result = mapStateToProps(mockStateWithFilters, props);
    });

    it('sets checkedValues on the props with the filter value for the categoryId', () => {
      expect(result.checkedValues).toBe(mockFilters);
    });

    it('sets checkedValues to empty object if no filters exist for the given resource', () => {
      result = mapStateToProps(mockStateWithOutFilters, props);
      expect(result.checkedValues).toEqual({});
    });

    it('sets checkedValues to empty object if no filters exist for the given category', () => {
      const props = setup({ categoryId: 'fakeCategory' }).props;
      result = mapStateToProps(mockStateWithFilters, props);
      expect(result.checkedValues).toEqual({});
    });
  });

  describe('mapDispatchToProps', () => {
    let dispatch;
    let result;
    beforeAll(() => {
      const props = setup().props;
      dispatch = jest.fn(() => Promise.resolve());
      result = mapDispatchToProps(dispatch);
    });

    it('sets clearFilterByCategory on the props', () => {
      expect(result.clearFilterByCategory).toBeInstanceOf(Function);
    });

    it('sets updateFilterByCategory on the props', () => {
      expect(result.updateFilterByCategory).toBeInstanceOf(Function);
    });
  });
});
